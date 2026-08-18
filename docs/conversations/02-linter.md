# Part 2: AI Deck Linter  (module: `opm_ai.linter`)

> Offline-first `Deck` parser + rule engine; `lint_deck` returns `LintResult` with structured issues and a boolean `passed`. Optional LLM enhancement adds plain-English explanations and top-of-deck summary comment.

## 1. Role in the AIM

- **Gatekeeper**: every deck produced by the Builder (Part 3) or pasted by a user must pass the linter before the Runner (Part 1) executes it. This gives students instant, deterministic feedback ("missing `/` terminator on `DX`") without needing an LLM API key.
- **Teacher**: the rule engine encodes veteran reservoir-engineer heuristics (WELSPECS group `AUTO` without `GRUPTREE`, negative `PERMX`, `WELSPECS`/`SCHEDULE` well mismatch, `PVTO`/`PVDO` phase mismatch with `RUNSPEC`). The optional LLM layer translates each `LintIssue` into a plain-English explanation with a suggested fix, written as a comment block at the top of the deck so the student sees it immediately.
- **Offline-first**: the rule engine is pure Python, zero external dependencies, and must run in CI without any API key. The LLM layer is additive and degrades gracefully to `None` (see `LLMClient` contract in 00-overview-and-architecture.md, 03-builder.md).

## 2. Position in build order

| | |
|---|---|
| Phase | Phase 1 (v1), Stage 2 - immediately after Stage 0 skeleton and Runner. v2 redesign (grammar-based engine + fix proposals + LinterAPI façade) followed in Phase 2 — see section 7 below. |
| Depends on | Stage 0 (`opm_ai` package importable, `settings.py` for optional LLM config) |
| Depended on by | Part 3 Builder (auto-lints every generated deck via `lint_deck`, L1-only), Part 6 CLI (`lint` subcommand), Part 6 FastAPI `/api/lint` + `/api/lint/apply-fix` routes, Part 6 Chat tool `tool_lint_deck` (routes through `LinterAPI.default_api.lint`) |

Cross-links: see 00-overview-and-architecture.md, 01-runner.md, 03-builder.md.

## 3. Hard API contract

Asserted by `tests/unit/test_linter.py` and specified in BUILD_GUIDE.md section 4.

```python
# opm_ai/linter/deck.py
class Deck:
    def __init__(self, deck_path: Path): ...
    @property
    def sections(self) -> list[str]: ...          # non-empty for SPE1
    def get_section(self, name: str) -> str | None: ...  # case-insensitive lookup

# opm_ai/linter/linter.py
def lint_deck(deck_path: Path) -> LintResult: ...

@dataclass
class LintResult:
    deck_path: str          # == str(deck_path)
    errors: list[LintIssue] # empty for valid SPE1 deck AND minimal sample deck
    passed: bool            # True iff len(errors) == 0
```

`LintIssue` (or `DeckDiagnostic`) is a dataclass/Pydantic model with at least:
`severity: Literal["ERROR", "WARNING", "INFO"]`, `section: str | None`, `keyword: str | None`, `line: int | None`, `message: str`.

**Critical nuance from the test fixtures**:

- `tests/fixtures/spe1/SPE1CASE1.DATA` - full valid black-oil deck (RUNSPEC, GRID, PROPS, SOLUTION, SUMMARY, SCHEDULE). `lint_deck` **must** return `passed=True`, `errors=[]`.
- Minimal sample deck in `test_lint_sample_deck` - has RUNSPEC, DIMENS, METRIC, GRID, DX/DY/DZ, PORO, PROPS, SCHEDULE but **NO SOLUTION and NO SUMMARY**. `lint_deck` **must still return `passed=True`, `errors=[]`**.

Therefore: **missing SOLUTION / SUMMARY cannot be a default ERROR**. They must be WARNING or INFO, or the rule must be conditional on the physics declared in RUNSPEC (e.g., SOLUTION required only when equilibrium initialization is expected).

## 4. Key design decisions

### 4.1 Parse strategy: hand-rolled section splitter (v1) vs `opm.io.Parser`

| Aspect | Hand-rolled splitter (chosen for v1) | `opm.io.Parser` (deferred) |
|--------|--------------------------------------|----------------------------|
| Offline testability | Pure Python, zero deps, runs in CI without OPM installed | Requires system `opm` Python bindings on the path |
| Speed | O(N) single pass, negligible | Parses full keyword records, slower |
| Fidelity | Section boundaries + raw text per section | Full keyword-level AST with types, defaults, aliases |
| Maintenance | ~150 lines for splitter + section index | Upstream handles keyword schema evolution |
| Extensibility | Rules operate on raw section text; keyword-level rules need a second pass | Rules can bind directly to typed `DeckItem` objects |

**Decision**: implement a fast, offline, pure-Python section splitter in `deck.py` (v1). Rules operate on raw section strings. Reserve `opm.io.Parser` as an optional deep-validation backend behind a feature flag (e.g., `OPM_LINTER_DEEP=1`) for v1.1+. This satisfies the "linter works offline" invariant (00-overview-and-architecture.md invariant table) and keeps the CI green without the system package.

**Algorithm sketch** (handles Eclipse/OPM deck quirks):
1. Read entire file as text (Eclipse decks are ASCII/UTF-8).
2. Normalize line endings; keep original line numbers.
3. Scan for section headers: `RUNSPEC`, `GRID`, `EDIT`, `PROPS`, `REGIONS`, `SOLUTION`, `SUMMARY`, `SCHEDULE`, `ENDFIN` (case-insensitive, word-boundary, not inside a quoted string or comment).
4. A section ends at the *next* section header or EOF. Keywords inside a section are terminated by `/` (not by newlines). Nested `/` inside string arrays (e.g., `ZCORN`) do not terminate keywords.
5. Store `(section_name, start_line, end_line, raw_text)` for each section.
6. `get_section(name)` returns the raw text (including internal `/` terminators) or `None`.

### 4.2 Two-stage pipeline: rule engine (authoritative) + optional LLM enhancement

```
lint_deck(deck_path)
    -> Deck(deck_path)                           # parse sections
    -> rule_engine.run(deck) -> list[LintIssue]  # deterministic, offline
    -> if settings.LLM_AVAILABLE:
           llm_summary = LLMClient().summarize_issues(issues)  # may return None
           if llm_summary: inject as top-of-deck comment
    -> LintResult(deck_path, errors=[i for i in issues if i.severity=="ERROR"], passed=...)
```

- Rule engine is **authoritative** for `passed`/`errors`. LLM never flips `passed`.
- LLM enhancement: single call with the structured issue list; prompt asks for (a) a 3-5 bullet executive summary, (b) per-issue plain-English explanation + suggested fix snippet. Result is a string inserted as a `/* LINT SUMMARY ... */` comment block at line 1 of the deck (non-invasive, ignored by Flow).
- LLM call **must not raise**; on any error/timeout/key-missing, return `None` and continue with rule-only result.

### 4.3 Severity model (ERROR / WARNING / INFO)

| Severity | Affects `LintResult.passed` | Typical use |
|----------|----------------------------|-------------|
| **ERROR** | Yes (`passed=False` if any) | Deck will not run: missing required keyword for declared physics, cross-reference failure (well in SCHEDULE not in WELSPECS), negative `PERMX`, missing terminating `/`, keyword/section mismatch (`PVTO` in RUNSPEC without `OIL`) |
| **WARNING** | No | Deck runs but likely wrong: missing SOLUTION/SUMMARY (conditional), `WELSPECS` group `AUTO` without `GRUPTREE`, inconsistent `WELOPEN` dates, `INCLUDE` path depth > 2, `DIMENS` product != product of `DX`/`DY`/`DZ` counts |
| **INFO** | No | Style/best practice: keyword not alphabetically ordered, `UNITS` defaulting to FIELD, comment style |

This model makes both test fixtures pass: the minimal sample deck has no ERRORs (it has RUNSPEC+GRID+PROPS+SCHEDULE which is a runnable depletion skeleton if SOLUTION defaults are accepted by Flow), while real problems are caught as ERROR.

### 4.4 Rule taxonomy (seed from `opm-flow-editor-support` + domain expertise)

Sources:
- `opm-flow-editor-support/scripts/` diagnostic rules (VS Code extension) - parse-time checks, keyword existence, section order.
- `tests/eclipse/` and `tests/eclipse_fileformat/` HTML references - keyword syntax, required sections per physics.
- SPE1 fixture (`tests/fixtures/spe1/SPE1CASE1.DATA`) - canonical valid deck.

**Concrete rule examples (10-15 to seed v1):**

| Rule ID | Severity | Section | Keyword / Pattern | Message (template) |
|---------|----------|---------|-------------------|-------------------|
| `L001` | ERROR | any | Missing terminating `/` on keyword (line ends without `/` before next keyword or section) | "Keyword `{kw}` at line {line} is missing terminating `/`" |
| `L002` | ERROR | RUNSPEC | `OIL`/`GAS`/`WATER` not declared but referenced in PROPS/SCHEDULE | "Phase `{phase}` used in `{section}` but not declared in RUNSPEC" |
| `L003` | ERROR | GRID | `DIMENS {nx} {ny} {nz}` product != count of `DX`/`DY`/`DZ` values | "DIMENS product ({n}) does not match {kw} value count ({count})" |
| `L004` | ERROR | GRID | `PERMX` / `PERMY` / `PERMZ` < 0 | "Negative permeability `{kw}`={value} at line {line}" |
| `L005` | ERROR | PROPS | `PVTO` present but `OIL` not in RUNSPEC (or `PVDO` with `DISGAS` missing) | "PVT table `{kw}` requires phase `{phase}` in RUNSPEC" |
| `L006` | ERROR | SCHEDULE | Well name in `WELSPECS` not found in `COMPDAT`/`WCONPROD`/`WCONINJE` | "Well `{well}` declared in WELSPECS has no completion or control" |
| `L007` | ERROR | SCHEDULE | Well name in `COMPDAT`/`WCONPROD`/`WCONINJE` not in `WELSPECS` | "Well `{well}` used in `{kw}` but not declared in WELSPECS" |
| `L008` | ERROR | SCHEDULE | `WELSPECS` group = `AUTO` but no `GRUPTREE` keyword in deck | "WELSPECS group AUTO requires GRUPTREE definition" |
| `L009` | WARNING | SOLUTION | No SOLUTION section and no `RESTART` | "Missing SOLUTION section; Flow will use default equilibration" |
| `L010` | WARNING | SUMMARY | No SUMMARY section | "No SUMMARY section; no time-series output will be written" |
| `L011` | WARNING | GRID | `PORO` values outside (0, 1] | "Porosity {value} at line {line} outside physical range (0, 1]" |
| `L012` | WARNING | PROPS | `SWOF`/`SGOF` endpoint `SWL`/`SGL` not consistent with `SATNUM` regions | "Saturation table endpoints inconsistent with region assignments" |
| `L013` | INFO | any | Keyword not in canonical Eclipse order within section | "Keyword `{kw}` appears out of recommended order" |
| `L014` | INFO | any | `INCLUDE` depth > 2 or absolute path | "Deep/absolute INCLUDE path may break portability" |
| `L015` | ERROR | RUNSPEC | `DIMENS` missing | "RUNSPEC must contain DIMENS keyword" |

Rules are pure functions: `def rule_L001(deck: Deck) -> list[LintIssue]`. The engine collects all issues, then `LintResult.errors = [i for i in issues if i.severity == "ERROR"]`, `passed = len(errors) == 0`.

### 4.5 LLM summary comment injection

- Prompt template (versioned in `opm_ai/linter/prompts/summarize.j2`):

```
You are a reservoir engineering teaching assistant. Given a list of structured lint issues
(severity, section, keyword, line, message), produce:
1. A 3-5 bullet executive summary for a student.
2. For each ERROR: a one-sentence plain-English explanation + a corrected keyword snippet.
3. For each WARNING: a brief "watch out" note.
Output as a single block comment suitable for the top of an Eclipse .DATA file:
/* LINT SUMMARY (auto-generated)
 * ...
 */
```

- Injected by `lint_deck` after rule engine runs, before returning `LintResult`. The deck text on disk is **not** modified; the comment is returned as an optional field `lint_summary: str | None` on `LintResult` (non-contract, used by Builder and CLI to show the user).

## 7. v2 architecture: grammar-based rule engine + fix-proposal pipeline

Sections 1-6 describe the v1 linter as shipped in 2026-07. Since 2026-08 the
linter is being rewritten (`docs/personal/LINTER_REDESIGN_PLAN.md`) to a
grammar-based, AST-aware engine that shares its rule catalogue with the
Builder and is callable from a future LangChain agent. This section captures
the v2 architecture as it stands today so a future reader does not mistake
v1 patterns for current state.

### 7.1 Module layout

```
opm_ai/linter/
  linter.py              # combined entry point (L1 + v2) — see 7.2
  deck.py                # v1 Deck class (sections splitter)
  models.py              # LintIssue, LintResult (v1-compatible shape, v2 adds fix_proposal)
  api.py                 # LinterAPI + default_api (sync + async, caching, executor pool)
  cache.py               # LinterCache (LRU 256, key includes catalogue_version)
  executor.py            # LinterExecutor (background thread pool, timeout-bounded)
  rules/                 # v1 L1 rule modules (kept for backward-compat)
  v2/
    parser.py            # tokenizer + section/keyword/record AST
    ast.py               # Deck / Section / Keyword / Record / Token dataclasses
    spec.py              # KeywordSpec / SizeKind / SectionName (hand-curated + keywords_rm.json hybrid)
    paths_aliases.py     # PATHS indexer
    resolver.py          # INCLUDE/IMPORT walker + CompositeDeck
    symbols.py           # SymbolTable builder (WELSPECS, GRUPTREE, FIPNUM, fluid tables, SUMMARY, FUNVAR, UDQ)
    validator.py         # rule engine — turns a parsed deck into lint issues
    fix_proposals.py     # FixProposal dataclass + propose_fix registry (per-rule-id proposers)
    self_heal.py         # LLM-assisted proposal scoring (used by /api/chat tool_lint_deck path)
    catalogue/           # keywords_rm.json + derived keyword_specs.json + _version.py
```

### 7.2 Entry points and the L1/v2 split

| Symbol | Where | What it runs | Used by |
|---|---|---|---|
| `lint_deck(path)` | `opm_ai/linter/linter.py` | **L1 only** (v1 rules) | Builder (`build_deck`, `build_deck_from_spec`) — intentionally NOT migrated |
| `lint_deck_combined(path)` | `opm_ai/linter/linter.py` | L1 then v2, dedup, return combined `LintResult` | Tests, default lint route on `/api/lint`, the apply-fix route |
| `LinterAPI.lint(path)` / `.lint_async(path)` | `opm_ai/linter/api.py` | Wraps `lint_deck_combined` with cache + executor + structured errors | Chat tools (`tool_lint_deck`, `tool_build_deck`) — preferred future entry point |
| `default_api` | `opm_ai/linter/api.py` | Singleton `LinterAPI` instance | Production callsites |

**Why the L1-only `lint_deck` stays exported from package level.** A previous
shim attempt (commit `83a430e`) looped: shim → facade → package surface that
imported the shim. Resolution (`968e8d9`): `lint_deck` is bound directly from
`opm_ai.linter.linter` in `opm_ai/linter/__init__.py`; the facade never
re-exports it. Builder callsites keep calling `lint_deck` L1-only because
migrating them to the combined/v2 path is a behaviour change (extra issues
fire that the Builder's prompts don't anticipate). Deferred, not forgotten.

### 7.3 LintIssue + FixProposal (v2 model)

`LintIssue` (v2) carries an optional `fix_proposal` field so the UI can offer
one-click remediation:

```python
class FixProposal:
    rule_id: str             # e.g. "L232"
    line: int                # 1-indexed, target line in the deck
    original_value: str      # current text on that line (drift guard)
    new_value: str           # proposed replacement
    description: str         # user-facing: "Set WELLDIMS to 1 well"
```

The proposers are registered in `opm_ai/linter/v2/fix_proposals.py` keyed by
`rule_id`. Each proposer receives the `LintIssue` + surrounding keyword
context and returns a `FixProposal | None`. The current coverage is the
common L1+v2 set; `None` means the issue cannot be auto-fixed (LLM may still
score a fix in the `self_heal` path — that's separate).

### 7.4 POST /api/lint/apply-fix — atomic one-click remediation

The endpoint is the user-facing surface for `FixProposal`. It is **not** a
re-implementation of the linter; it asks the v2 proposers to re-compute the
proposal, drift-checks against the client-supplied values, applies it, and
returns the patched deck + a fresh `LintResult` in one round-trip.

**Request**
```json
{
  "deck_path": "<allowlisted server-side path>",
  "rule_id": "L232",
  "line": 5,
  "original_value": "1 1 1 1 1 /",
  "new_value": "3 1 1 1 1 /"
}
```

**Responses**
- `200 OK` — `{deck_text: str, lint: LintResult}` — patch applied, fresh lint attached so the UI replaces its state without a second `/lint` round-trip.
- `400 Bad Request` — bad `deck_path`, bad `rule_id` format (must match `^L\d+$`), or any missing field.
- `404 Not Found` — `deck_path` not on the allowlist.
- `409 Conflict` — server-recomputed `FixProposal.original_value` ≠ client `original_value` (deck text drifted since the user opened the lint panel). Deck is **not** written; client should re-lint and retry.
- `422 Unprocessable Entity` — server cannot compute a proposal for this `rule_id` + `line` (no proposer, or proposer's view of the deck disagrees with the client's). Deck is not written.

**Three-stage server-side validation** (all in `opm_ai/api/routes/lint.py::apply_fix_endpoint`):

1. **Path allowlist** — same `validate_deck_path` helper used by `/api/lint`, rejecting anything outside the configured deck roots.
2. **Rule-id shape** — must match `^L\d+$` so a malformed value cannot reach the proposer registry.
3. **Drift check** — re-run `propose_fix(rule_id, issue, deck_text)` server-side; if `proposal.original_value != request.original_value`, return 409 and skip the write. This prevents the UI from clobbering a line that has been edited concurrently.

After all three pass, `apply_proposal_to_text` rewrites the deck in memory,
the new text is written back to disk atomically (write-then-rename), and the
fresh `LintResult` is computed and returned.

### 7.5 Frontend integration

- `frontend/src/types.ts` — `FixProposalView`, `ApplyFixRequest`, `ApplyFixResponse`; `LintIssue.fix_proposal?: FixProposalView`.
- `frontend/src/api/client.ts` — `api.applyFix(request)`.
- `frontend/src/components/LinterPanel.tsx` — "Apply Fix" button rendered next to each issue whose `fix_proposal` is non-null. On click: `setApplyingRuleId(rule_id)`, call `api.applyFix`, replace `deckText` and `lintResult` from the response, clear the spinner. The button is disabled globally while any apply is in flight so concurrent clicks are dropped rather than raced.

### 7.6 Tests covering 7.4 / 7.5

`tests/integration/test_api_lint_apply_fix.py` — 5 tests:

| Test | What it asserts |
|---|---|
| `test_apply_fix_l232_happy_path` | WELLDIMS 1 → 3 wells; response carries patched `deck_text` and a fresh `LintResult` with the L232 issue gone; deck file on disk is the new text |
| `test_apply_fix_returns_409_on_drift` | Client `original_value` differs from server-computed; response is 409; deck file is unchanged |
| `test_apply_fix_rejects_path_outside_allowlist` | `deck_path` outside the allowlist → 400 |
| `test_apply_fix_rejects_bad_rule_id` | `rule_id = "not-an-id"` → 400 |
| `test_apply_fix_returns_422_when_no_proposal` | Server cannot compute a proposal for the supplied `(rule_id, line)` → 422 |

`tests/integration/test_api_lint_route.py` — 2 tests updated to patch the
renamed `lint_deck_combined` symbol instead of the old `lint_deck_func`
(private name) that the integration tests used to reach into.

## 5. Toolchain grounding

| Item | Path / version | Used by | Status |
|------|----------------|---------|--------|
| SPE1 fixture | `tests/fixtures/spe1/SPE1CASE1.DATA` | Tests, rule calibration | VERIFIED |
| Eclipse keyword refs | `tests/eclipse/`, `tests/eclipse_fileformat/` | Rule authoring | VERIFIED (HTML) |
| `opm-flow-editor-support` scripts | UNVERIFIED (external repo) | Rule seed | Check at impl: clone or vendor key scripts |
| `opm.io.Parser` | `/usr/lib/python3/dist-packages/opm/io/` | Optional deep mode | UNVERIFIED exact API; v1 uses hand-rolled |
| `LLMClient` | `opm_ai.llm.client` | Optional enhancement | Contract in 00-overview-and-architecture.md |
| `settings` | `opm_ai.settings.Settings` | LLM availability, log level | Stage 0 |

## 6. Implementation approach

Files to create under `opm_ai/linter/`:

1. `__init__.py` - exports `Deck`, `lint_deck`, `LintResult`, `LintIssue`.
2. `deck.py` - `Deck` class with hand-rolled section splitter.
   - `__init__(self, deck_path: Path)`: read file, parse sections, store list of `(name, start_line, end_line, text)`.
   - `sections` property: list of section names in order.
   - `get_section(name: str) -> str | None`: case-insensitive lookup, returns raw text.
3. `models.py` - `LintIssue` (dataclass/Pydantic), `LintResult` (dataclass).
4. `rules/` - package with one module per rule group or a single `registry.py` with `RULES: list[Callable[[Deck], list[LintIssue]]]`.
   - `registry.py`: imports all rule functions, exposes `run_all(deck) -> list[LintIssue]`.
   - Individual rule modules: `grid.py`, `props.py`, `schedule.py`, `runspec.py`, `solution_summary.py`, `general.py`.
5. `linter.py` - `lint_deck(deck_path) -> LintResult` orchestrator.
   - Calls `Deck(deck_path)`, `rules.run_all(deck)`.
   - Splits issues into `errors` (severity==ERROR) and others.
   - If `settings.LLM_AVAILABLE`: calls `llm.summarize_issues(issues)` (graceful fallback to `None`).
   - Returns `LintResult(deck_path=str(deck_path), errors=errors, passed=len(errors)==0, lint_summary=summary)`.
6. `prompts/summarize.j2` - Jinja2 template for the LLM summary prompt.
7. `context.md` - per-folder context (CLAUDE.md rule).

Order of work (TDD against `test_linter.py`):
1. Implement `Deck` parser in `deck.py` to make `test_parse_spe1_deck` pass.
2. Implement `LintIssue`, `LintResult`, and a stub `lint_deck` returning `passed=True, errors=[]` to make `test_lint_spe1_deck` pass.
3. Add rule engine skeleton and the minimal rules needed to keep the sample deck clean (no ERROR rules fire on the minimal deck).
4. Add the 15 seed rules incrementally; verify SPE1 stays clean.
5. Wire optional LLM enhancement behind `settings.LLM_AVAILABLE`.
6. Add `lint_summary` field to `LintResult` (non-breaking).

## 7. Risks and open questions

| Risk / question | Impact | Mitigation |
|-----------------|--------|------------|
| Hand-rolled parser misses edge cases (`INCLUDE`, `ENDINCLUDE`, comments, continuation lines, `ZCORN` with embedded `/`) | False positives/negatives in section boundaries | Test against all 110 fixture decks; fall back to `opm.io.Parser` behind flag if needed |
| Severity model: is missing SOLUTION truly WARNING for all physics? | Could mask a real error for equilibrium runs | Make SOLUTION WARNING conditional: ERROR if `EQUIL` or `RPTRST` in deck, else WARNING |
| Rule explosion: 50+ rules may slow lint | CLI responsiveness | Rules are O(deck size); 110 decks x <10 KB each is trivial. Profile if needed. |
| LLM summary quality without few-shot examples | Poor explanations | Add 3-5 curated (deck, issues, ideal_summary) examples to prompt in v1.1 |
| `LintResult` contract: test only checks `errors` and `passed`; `lint_summary` is extra | Safe to add | Keep extra field optional; no test changes needed |
| `opm-flow-editor-support` rules not yet vendored | Seed rule set incomplete | Start with the 15 concrete rules above; import editor-support rules in a follow-up PR |

## 8. Verification and done-criteria

Gating test: `tests/unit/test_linter.py`.

```bash
cd /home/parallels/opm-ai
pytest tests/unit/test_linter.py -v
```

Must pass:
- `test_parse_spe1_deck` - `Deck` parses SPE1, `sections` non-empty, `get_section("RUNSPEC")` and `get_section("GRID")` non-None.
- `test_lint_spe1_deck` - `lint_deck` returns `LintResult` with `deck_path == str(spe1_path)`, `errors == []`, `passed == True`.
- `test_lint_sample_deck` - minimal deck (no SOLUTION, no SUMMARY) returns `passed == True`, `errors == []`.

Additional manual verification:
- Run `lint_deck` on a deliberately broken deck (e.g., missing `/` on `DX`, negative `PERMX`, well in SCHEDULE not in WELSPECS) and assert `passed == False` with structured `LintIssue` objects.
- Run with `GROQ_API_KEY` unset -> LLM enhancement returns `None`, rule-only result unchanged.
- Run with `GROQ_API_KEY` set -> `lint_summary` populated, comment block well-formed.

## 9. Future extensions

- Deep mode: optional `opm.io.Parser` backend for keyword-level validation (defaults, aliases, enum values).
- Auto-fix: for deterministic rules (missing `/`, keyword case, ordering), emit a corrected deck via `--fix` CLI flag.
- Incremental linting: cache section hashes; re-lint only changed sections (editor integration).
- Extended rule packs: EOR-specific (POLYMER, SURFACT), thermal, CO2STORE, Foam - loaded as plugins.
- LSP integration: expose rule diagnostics via Language Server Protocol for VS Code / editors.
- Teaching mode: group issues by "concept" (grid, wells, PVT, schedule) and show mini-lessons per group.

---