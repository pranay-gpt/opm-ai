# Linter-as-Tool: Design Spec

**Date**: 2026-08-18
**Status**: Draft (pending user review)
**Author**: Brainstorming session
**Subsystem scope**: Linter module (the v1 + v2 linters and their consumers)
**Sibling specs**: LangChain orchestration (next), Playwright E2E (after)

---

## 0. Context

OPM-AI has two linter implementations (v1 in `opm_ai/linter/rules/`, v2 in `opm_ai/linter/v2/`) that already run together via `lint_deck_combined`. They are called from:

- `opm_ai/builder/builder.py:394, 430` (after every build)
- `opm_ai/api/routes/lint.py:35` (POST `/api/lint`)
- `opm_ai/api/routes/chat.py:80, 98` (LLM chat tools `tool_lint_deck`)

A code review (commit `3dfe17f` + subsequent review) surfaced 15 findings: 6 correctness bugs, 4 perf/architecture gaps, 5 memory/hygiene issues. The user wants to fix all 15 and make the linter callable as a clean tool by a future LangChain agent.

## 0.1 Why this spec exists

The current "linter" is exposed as a function (`lint_deck(path) -> LintResult`) that is reused across three call sites. Without a facade, every caller hand-rolls the same boilerplate (executor pool, cache key, error conversion). The future LangChain agent will need a richer interface (async, with-explanation). The right time to formalize the public API is before the second caller of the LangChain-style entry point appears.

**Note on input shape**: the LangChain agent will operate on in-memory text strings, not files. For this spec, the input is always a file path (`str | Path`). The agent is responsible for writing its in-memory text to a temp file before calling `LinterAPI`. Doing this in the spec would require agreeing on the temp-file policy (under what dir, with what cleanup), which is a separate concern. If the agent's temp-file flow becomes contentious, the LangChain spec can extend `LinterAPI` with a `lint_text(text: str) -> LintResult` entry point.

## 0.2 Scope boundaries

This spec is **only** about the linter module. It does not:

- Define the LangChain agent loop (sibling spec).
- Cover the Playwright UI tests (sibling spec).
- Touch the existing `lint_deck_combined` orchestration (preserved as-is).
- Redesign the v1 or v2 linter rules (only fixes the 15 findings).

---

## 1. Architecture

**One new module**: `opm_ai/linter/api.py` — a facade that exposes the public tool-calling API and hides the v1/v2 split, the cache, and the executor pool.

```
                    ┌────────────────────────────────────────────┐
                    │  LinterAPI  (opm_ai/linter/api.py)         │
                    │                                            │
   lint(path) ─────►│  ┌─────────┐  ┌────────────┐  ┌────────┐  │
   lint_async(...) ─┼─►│  cache  │─►│ executor   │─►│ lint() │  │
   lint(...,        │  │ (sha256 │  │ (4 workers)│  │ v1+v2  │  │
   with_explain)  ──┼─►│  + cat  │  │            │  │combin.)│  │
                    │  │ version)│  └────────────┘  └────────┘  │
                    │  └─────────┘                                │
                    │       │ miss                                 │
                    │       ▼                                     │
                    │  ┌──────────────┐                           │
                    │  │  explainer   │ (if with_explanation)     │
                    │  └──────────────┘                           │
                    └────────────────────────────────────────────┘
```

### 1.1 Boundaries

- `LinterAPI` does NOT call the LLM. It returns `LintResult`. The chat tool layer is upstream.
- `LinterAPI` does NOT call the builder. It is a callee of the builder.
- `LinterAPI` does NOT own the calibration temp dir, the proposal files, or any background job. That is a different scope.

### 1.2 Why this shape

The future LangChain agent will call `LinterAPI.lint_async(...)` as a tool. The current chat tools (`tool_lint_deck`) call `LinterAPI.lint(...)` via `asyncio.to_thread`. The DeckBuilder → lint path becomes `LinterAPI.lint(...)` directly. One interface, three call sites, same behaviour.

---

## 2. Components

### 2.1 `LinterAPI` (`opm_ai/linter/api.py`, new)

~150 lines. The public face.

```python
class LinterAPI:
    def __init__(self, *, max_workers: int = 4, cache_size: int = 256,
                 linter_timeout_s: float = 30.0): ...

    def lint(self, source: str | Path, *,
             with_explanation: bool = False,
             incremental_of: Path | None = None) -> LintResult: ...

    async def lint_async(self, source: str | Path, *,
                         with_explanation: bool = False,
                         incremental_of: Path | None = None) -> LintResult: ...

    def invalidate_cache(self, source: Path | None = None) -> None: ...

    def cache_stats(self) -> CacheStats: ...

# Module-level singleton for the common case
default_api = LinterAPI()

# Convenience aliases (preserves existing imports)
def lint_deck(path: Path) -> LintResult:
    return default_api.lint(path)
```

### 2.2 `LinterCache` (`opm_ai/linter/cache.py`, new)

- Key: `(path, content_sha256, catalogue_version)`
- Value: `LintResult`
- LRU eviction at 256 entries (configurable via settings)
- Thread-safe (single `threading.Lock`; the cache is a dict, small ops)
- Returns a `copy.deepcopy` of the cached `LintResult` (not the same instance)

### 2.3 `LinterExecutor` (inside `api.py`)

Single `ThreadPoolExecutor(max_workers=4)` at module init. Sync `lint` calls `executor.submit(...).result()` with timeout. Async path uses `asyncio.to_thread` (no separate executor).

### 2.4 `catalogue_version()` (in `opm_ai/linter/v2/catalogue/keywords.py`)

Bumped on every `_register()` call and on `reset_keyword_index()`. Makes the cache self-invalidating when the catalogue changes (the lesson from the L201 fix).

---

## 3. Public API contract

### 3.1 Inputs

- `source: str | Path` — if `str`, must be valid file path. If `Path`, must exist.
- `with_explanation: bool = False` — when True, each issue carries an `explain: str | None` field populated by `opm_ai.explainer.explainer.explain()`. Hook for the future LangChain agent.
- `incremental_of: Path | None` — when set, the lint is treated as a delta from the file at `incremental_of`. For now this is a no-op that calls full lint; the parameter exists so the future incremental implementation can hook in without an API change.

### 3.2 Output

`LintResult` (existing Pydantic model, no schema change). Already has `passed`, `errors`, `warnings`, `info`, `deck_path`, `issues[].code`, `issues[].message`, `issues[].severity`, `issues[].line`, `issues[].keyword`.

### 3.3 Re-exports for back-compat

- `from opm_ai.linter import lint_deck, LintResult, LintIssue` — keeps working. `lint_deck` becomes a thin wrapper around `default_api.lint(path)`.
- `from opm_ai.linter.linter import lint_deck_v2, lint_deck_combined` — direct access to the underlying orchestrator still works.
- `from opm_ai.linter.api import LinterAPI` — new import for the facade.

### 3.4 Settings

In `opm_ai/settings.py`:

```python
class Settings:
    linter_max_workers: int = 4
    linter_cache_size: int = 256
    linter_timeout_s: float = 30.0
    linter_cache_enabled: bool = True
```

---

## 4. Data flow

For `lint(path)`:

1. Validate `path` exists, is a file, is readable.
2. Read text, compute `sha256(text)`.
3. Compose cache key: `(path, sha256, catalogue_version())`.
4. Lookup. If hit: return a `copy.deepcopy` of the cached `LintResult`.
5. If miss: submit to executor. Wait for result. Store. Return.

### 4.1 Error handling

- `FileNotFoundError` → `LintResult` with one ERROR-level issue (machine-readable).
- Parse crash → caught and converted to a synthetic LintIssue (today's behaviour, preserved).
- Executor timeout → `LintResult` with one ERROR-level issue + log warning.
- Cache corruption (unpicklable value) → log, evict, retry once.

---

## 5. The 15 fixes, mapped

| # | Finding | Where it gets fixed |
|---|---|---|
| 1 | L201 bypass for 6 keywords | `rules/shape.py:57` — extend L201 to LIST-keyword minimum-record check |
| 2 | Missing `precise_items=True` | `catalogue/keywords.py:991-2646` — add to all 6 changed keywords |
| 3 | L202 no-min check | `rules/shape.py:84` — add `len(rec.items) < expected_items` branch |
| 4 | self_heal composition bug | `v2/self_heal.py:339-377` — pass cumulative patched text |
| 5 | ThreadPoolExecutor race | `v2/calibration.py:24-26` — replace dict/list with `queue.Queue` or actor model |
| 6 | `_DECK_CACHE` shared instance | `linter/api.py` — new cache returns deepcopy |
| 7 | No cache in lint_deck_v2 | `linter/api.py` — `LinterCache` |
| 8 | INCLUDE re-tokenize | `v2/resolver.py:217` — `LinterCache` covers it (same key) |
| 9 | Eager rule registration | `v2/validator.py:117` — lazy register on first validate() |
| 10 | Resolver state isolation | `v2/resolver.py:113` — new Resolver per call (verify) |
| 11 | Cache shared instance | `linter/api.py` — deepcopy (same as #6) |
| 12 | Calibration temp dir leak | `v2/calibration.py:479` — try/finally + atexit |
| 13 | Unbounded cache | `v2/calibration.py:478` — LRU on calibration cache |
| 14 | Proposal-file pollution | `v2/self_heal.py:270` — write to tempdir, not source dir |
| 15 | KEYWORD_INDEX no reset | `catalogue/keywords.py:5304` — add `reset_keyword_index()` |

### 5.1 Cross-cutting

- The `catalogue_version()` bump makes fixes #1, #2, #3 self-invalidating. If a developer changes the catalogue, the cache flushes automatically.
- The deepcopy on cache hit (fix #11) makes the cache safe for any caller, including the future LangChain agent that will mutate the result downstream.

---

## 6. Migration

Existing callers (`api/routes/lint.py`, `api/routes/chat.py:80`, `builder/builder.py:394, 430`) get switched to `LinterAPI.lint_async(...)` or `LinterAPI.lint(...)` as appropriate. No caller behaviour change.

Step-by-step:

1. Add `LinterAPI` and `LinterCache` to `opm_ai/linter/`. No external imports yet.
2. Add `reset_keyword_index()` and `catalogue_version()` to the catalogue.
3. Fix the 15 findings in the underlying modules.
4. Wire `LinterAPI` into the three call sites.
5. Move `from opm_ai.linter.linter import lint_deck` to `from opm_ai.linter.api import lint_deck`.
6. Remove the old `_DECK_CACHE` in `opm_ai/linter/linter.py` (replaced by `LinterCache`).

Each step is a separate commit. The 814 unit tests + 610 corpus fixtures stay green at every step.

---

## 7. Testing strategy

### 7.1 Unit tests (`tests/unit/test_linter_api.py`, new)

Per-entry-point tests:

- `test_lint_path_returns_lintresult`
- `test_lint_async_returns_lintresult`
- `test_lint_with_explanation_attaches_explain_field`
- `test_lint_incremental_of_is_no_op_for_now`
- `test_lint_str_path_when_not_a_file_raises_filenotfound`
- `test_lint_async_can_be_awaited_concurrently`

Cache tests:

- `test_cache_hit_returns_copy_not_same_instance`
- `test_cache_hit_is_observable_via_cache_stats`
- `test_cache_miss_on_path_change`
- `test_cache_miss_on_content_change`
- `test_cache_miss_on_catalogue_version_bump`
- `test_cache_miss_on_explicit_invalidate`
- `test_cache_invalidate_all_flushes`
- `test_cache_lru_eviction_at_max_size`
- `test_cache_stats_reports_hits_misses_size`

Executor tests:

- `test_executor_pool_size_is_respected`
- `test_executor_timeout_returns_lintresult_with_error_issue`
- `test_executor_handles_parse_crash`

### 7.2 Catalogue fix tests (`tests/unit/test_catalogue_fixes.py`, new)

One test per finding (15 total). Each test pins the fix and targets the specific bug.

### 7.3 Corpus regression (`tests/integration/test_corpus_clean.py`, expanded)

- Existing: 610/610 known-good fixtures clean. Stays green.
- Add: snapshot of lint time per fixture (mean + p95). Committed baseline.
- Add: cache-hit-rate metric. Committed as `tests/integration/corpus_cache_baseline.json`.

### 7.4 Property-based fuzz (`tests/unit/test_linter_fuzz.py`, new)

`hypothesis` library. Generate random valid decks (start with a SPE1 fixture, mutate 0-3 keywords). Properties:

- `lint(deck)` never crashes. Returns a `LintResult` with `isinstance(issues, list)`.
- `lint(deck)` is deterministic for the same input (same content_sha256 → same result).
- Cache hit does not modify cached result on subsequent calls.

### 7.5 Test isolation

- `LinterAPI` is instantiated per test class (owns a cache and executor).
- `default_api` singleton is patched in tests via `monkeypatch.setattr(opm_ai.linter.api, "default_api", test_api)`.

### 7.6 Existing tests stay green

All 814 unit tests pass after the migration. All 610 corpus fixtures clean. The 15 fixes are individually tested; regressions are pinpointed.

---

## 8. Risks

- **Pool exhaustion**: a slow lint on a 10-INCLUDE deck could occupy a worker for 30s. With max_workers=4, 4 simultaneous slow lints and the executor is saturated. Mitigation: `linter_timeout_s` bounds the wait. The async path uses `asyncio.to_thread` which is bounded by the global default executor pool.
- **Cache invalidation gap**: editing a file via `:w` in vim bumps mtime but the cache key is sha256, so miss is guaranteed. Editing via `sed -i` in-place: same. The risk is *not* stale results; the risk is *cache miss + full re-lint* on every save. Acceptable.
- **Thread-pool overhead**: each `lint` call goes through a lock + executor.submit. For a 5ms lint, overhead dwarfs the work. Mitigation: small paths (cache hit fast path) skip the executor.
- **catalogue_version() race**: if two threads bump the version concurrently, the int counter is atomic in CPython but the mutation to `KEYWORD_INDEX` is not. Mitigation: `reset_keyword_index()` and `_register()` both hold the same lock when bumping. The cache self-invalidates on next lookup anyway.

---

## 9. Out of scope

- The LangChain agent loop and tool registry (sibling spec).
- Playwright UI tests (sibling spec).
- v2 linter rule redesign beyond the 15 fixes.
- Calibration self-heal UI integration.
- The `lint_deck_combined` orchestrator internals (preserved as-is).

---

## 10. Success criteria

- All 15 findings are fixed and individually tested.
- The 814 pre-existing unit tests + 610 corpus fixtures stay green.
- `LinterAPI` is the canonical call site for the builder, chat, and any new caller.
- The deep-copy invariant on cache hit is verified by a test.
- `catalogue_version()` makes cache invalidation automatic on catalogue changes.
- The future LangChain agent can call `await LinterAPI().lint_async(path, with_explanation=True)` and get a `LintResult` with `explain` field populated.
