# Part 3 - Builder, LLM Client & CLI  (modules: `opm_ai.builder`, `opm_ai.llm`, `opm_ai.cli`)

> Natural-language -> OPM Flow deck generation, shared LLM client, and Typer/Click CLI.

---

## 1. Role in the AIM

The **Builder** turns a student's plain-English description ("10x10x5 depletion with one producer") into a valid OPM Flow `.DATA` deck that passes the **Linter** (Part 2) and can be executed by the **Runner** (Part 1).  
The **LLM Client** provides a provider-agnostic `chat()` interface (Groq, OpenAI-compatible/NVIDIA NIM, offline fallback) used by the Builder's online extraction path and later by the Chat API (Part 6).  
The **CLI** exposes `lint`, `build`, `run` commands so the whole loop works from a terminal without the web UI.

---

## 2. Position in Build Order

| Phase | Stage | This Part | Depends On | Depended On By |
|-------|-------|-----------|------------|----------------|
| 1 v1  | 3     | Builder + LLM + CLI | Runner (1), Linter (2), `settings.py` (0) | FastAPI routes `/api/build`, `/api/lint`, `/api/run` (Phase 2) |

---

## 3. Hard API Contract (from tests)

### `opm_ai.builder.extract.extract_parameters_offline`

```python
def extract_parameters_offline(desc: str) -> ModelSpec:
    ...
```

**Assertions** (`tests/integration/test_builder.py::test_extract_parameters_offline`):

- `spec.scenario == "depletion"`
- `spec.reservoir.nx == 10`, `ny == 10`, `nz == 5`  (parsed from `"10x10x5"`)
- `len(spec.wells) == 1`
- `spec.wells[0].well_type == "PROD"`

### `opm_ai.builder.builder.build_deck`

```python
def build_deck(
    desc: str,
    output_path: Path | None = None,
) -> tuple[str, LintResult]:
    ...
```

**Assertions** (`tests/integration/test_builder.py::test_build_deck_depletion`):

- `deck_string` contains sections: `RUNSPEC`, `GRID`, `PROPS`, `SOLUTION`, `SCHEDULE`
- `lint_result.passed is True`
- `lint_result.errors == []`
- File written when `output_path` provided

### `opm_ai.llm.client.LLMClient`

```python
class LLMClient:
    def __init__(self) -> None: ...              # never raises
    def chat(self, messages: list[dict]) -> str | None: ...  # None if offline
    @property
    def available(self) -> bool: ...
```

**Assertions** (`tests/unit/test_llm.py`):

- Construction succeeds without API keys
- `.chat([{"role": "user", "content": "test"}])` returns `None` or `str`
- `.available` is `bool`

### `opm_ai.cli.main` (Click group)

**Assertions** (`tests/unit/test_cli.py`):

- `main --help` output contains `"OPM-AI"`
- `main lint <spe1_deck>` -> exit 0, prints `"Passed"`
- `main build "5x5x3 depletion" -o <file>` -> exit 0, writes file, prints `"Lint passed"`

---

## 4. Key Design Decisions

| # | Decision | Rationale | Alternatives Considered | Consequences |
|---|----------|-----------|------------------------|--------------|
| 1 | **Two-path extraction**: strict Pydantic `ModelSpec` + offline regex/heuristic path (default) + online LLM function-calling path (opt-in) | Tests run offline; hallucination prevented by schema validation; LLM adds richness when available | Single LLM-only path; template-only (no extraction) | Offline path must satisfy full contract (it does); online path deferred to Phase 2 |
| 2 | **Single Jinja2 template** (`base.j2`) seeded from SPE1 fixture | SPE1 is the canonical black-oil depletion case; one template that lints clean is better than many half-baked ones | Multiple scenario-specific templates now | v1 ships depletion-only; roadmap of 8-12 templates (5-spot, line-drive, WAG, gas-cap, CO2, multilayer, buildup) tracked in `IMPLEMENTATION_PLAN.md` |
| 3 | **Template context computed in `_compute_template_context()`** | Keeps `build_deck()` thin; allows `build_deck_from_spec()` for programmatic use | Inline rendering logic | Clear separation; easy to test context independently |
| 4 | **LLM client initialises both Groq & OpenAI clients lazily** | `available` reflects any configured provider; graceful offline fallback; no hard dependency on either SDK | Single provider hard-coded; factory pattern | Slight complexity in `__init__`, but callers see uniform interface |
| 5 | **Click (not Typer) for CLI** | Existing tests import `click`; Click is stable, zero-dependency | Typer (modern, but adds pydantic dep) | `pyproject.toml` must add `click` (currently missing) |
| 6 | **Builder auto-lints** (calls `lint_deck` on generated deck) | Guarantees `lint_result.passed == True` for v1 output; fails fast | Separate lint step required by user | Slight perf cost (temp file); acceptable for deck sizes < 100 KB |
| 7 | **Pydantic `ModelSpec` with defaults matching SPE1** | `extract_parameters_offline` only overrides parsed values; unspecified fields get SPE1-like defaults | Require all fields in description | Robust to underspecified input; deck always runnable |

---

## 5. Toolchain Grounding

| Item | Path / Version | Verified |
|------|----------------|----------|
| OPM Flow binary | `/usr/bin/flow` (2026.04, Ubuntu 24.04, OpenMPI 4.1.6) | verified |
| Python OPM bindings | `/usr/lib/python3/dist-packages/opm/` (`opm.io`, `opm.simulators`) | verified |
| ResInsight gRPC | `/usr/bin/ResInsight` port 50051 (`rips` client) | verified |
| Reference decks | `tests/fixtures/` (clone of `opm-tests`, 110+ cases) | verified |
| SPE1 fixture | `tests/fixtures/spe1/SPE1CASE1.DATA` (FIELD, OIL/GAS/WATER/DISGAS, 10x10x3, 300 cells) | verified |
| Jinja2 | >=3.1 (stdlib-compatible) | verified |
| Pydantic | >=2.7 (v2 API) | verified |
| Click | >=8.1 (required by tests, **missing from pyproject.toml**) | WARNING UNVERIFIED - add to deps |
| Groq SDK | `groq` package (if `GROQ_API_KEY` set) | Optional |
| OpenAI SDK | `openai` >=1.0 (for NIM compatible endpoint) | Optional |

**UNVERIFIED items to check at implementation time:**

- `click` version compatibility with Python 3.12 (tests pass with 8.1+)
- Whether `resfo` (>=5.0) is importable for post-process (Phase 2)
- Exact `opm.io.Parser` API for deck parsing (currently using regex in linter)

---

## 6. Implementation Approach (concrete steps)

### 6.1 Package skeleton (Stage 0)
```
opm_ai/
|-- __init__.py
|-- settings.py          # pydantic-settings, .env loading
|-- cli.py               # Click group: lint / build / run
|-- llm/
|   |-- __init__.py
|   |-- client.py        # LLMClient (Groq + OpenAI + offline)
|-- builder/
|   |-- __init__.py
|   |-- models.py        # ModelSpec, ReservoirSpec, WellSpec, enums
|   |-- extract.py       # extract_parameters_offline()
|   |-- builder.py       # build_deck(), build_deck_from_spec()
|   |-- templates/
|       |-- base.j2      # SPE1-derived Jinja2 template
|-- linter/
|   |-- __init__.py
|   |-- deck.py          # Deck parser, LintResult, LintError
|   |-- linter.py        # lint_deck() rule engine
|-- runner/
|   |-- __init__.py
|   |-- models.py        # SimulationJob, SimulationResult, CrashReport
|   |-- runner.py        # run_simulation() subprocess wrapper
|-- ... (postprocess, preprocess, explainer, api - later phases)
```

### 6.2 Models (`builder/models.py`)
- `ScenarioType` enum: `DEPLETION`, `WATERFLOOD_5SPOT`, `LINE_DRIVE`, `WAG`, `GAS_CAP`, `CO2_EOR`, `MULTILAYER`, `BUILDUP`
- `ReservoirSpec`: nx/ny/nz (with SPE1 defaults), geometry arrays, properties per layer
- `WellSpec`: name, type (PROD/INJ), i/j/k1/k2, reference_depth, control params
- `ModelSpec`: scenario, title, reservoir, wells[], start_date, timesteps[], field_units

### 6.3 Offline extraction (`builder/extract.py`)
- Regex for grid: `(\d+)\s*[xX]\s*(\d+)\s*[xX]\s*(\d+)`
- Keyword scanning for scenario: depletion / waterflood / line-drive / WAG / gas-cap / CO2 / multilayer / buildup
- Well heuristics:
  - Depletion: 1 producer at (nx, ny, nz)
  - SPE1-like: injector (1,1,1) GAS + producer (nx,ny,nz) OIL
  - 5-spot: injector center, 4 corner producers
  - Line-drive: injector (1, ny/2), producer (nx, ny/2)
- Returns fully-populated `ModelSpec` (Pydantic validates)

### 6.4 Template (`builder/templates/base.j2`)
- Sections: RUNSPEC, GRID, PROPS, SOLUTION, SCHEDULE
- FIELD units, black-oil (OIL GAS WATER DISGAS)
- PVT tables copied from SPE1 fixture
- Relative permeability (SWOF/SGOF) from SPE1
- EQUIL at 8400 ft / 4800 psia
- WELSPECS + COMPDAT for all wells
- WCONPROD / WCONINJE with rate/BHP controls
- TSTEP: monthly for 1 yr, then quarterly (loop renders `loop.index % 6`)

### 6.5 Builder (`builder/builder.py`)
- `build_deck(desc, output_path)` -> calls `extract_parameters_offline`, renders template, writes file if path given, lints via temp file, returns `(deck_str, LintResult)`
- `build_deck_from_spec(spec, output_path)` -> programmatic API for tests/FastAPI

### 6.6 LLM Client (`llm/client.py`)
- Reads `settings.groq_api_key`, `settings.openai_api_key/base_url`
- Tries Groq first, then OpenAI-compatible
- `.chat()` returns `str` or `None` (never raises)
- `.available` = `bool(groq or openai client)`

### 6.7 CLI (`cli.py`)
- Click group `main`
- `lint <deck>` -> calls `lint_deck`, prints "Passed" or errors, exit code
- `build "<desc>" -o <file>` -> calls `build_deck`, writes file, prints "Lint passed"
- `run <deck> -o <dir> -t <timeout>` -> calls `run_simulation`, prints result

---

## 7. Risks & Open Questions

| Risk | Mitigation |
|------|------------|
| Offline extraction misses nuance (faults, regions, aquifers) | v1 scope is simple decks; advanced features via LLM path (Phase 2) or manual deck edit |
| Template drift from OPM Flow version changes | Linter catches invalid keywords; SPE1 fixture is regression anchor |
| `click` missing from `pyproject.toml` | Add `click>=8.1` before Stage 3 commit |
| Jinja2 `loop.index` vs `enumerate` in TSTEP | Use `loop.index` (1-based) - already fixed in template |
| LLM provider selection logic when both keys set | Current: Groq first, then OpenAI; document in `settings.py` |
| Runner omits `--threads` (per GUIDE 1) - verify no perf regression | Document in `runner/runner.py`; benchmark later |

---

## 8. Verification & Done Criteria

| Test File | Command | Must Pass |
|-----------|---------|-----------|
| `tests/unit/test_llm.py` | `pytest tests/unit/test_llm.py -v` | verified 3/3 |
| `tests/unit/test_cli.py` | `pytest tests/unit/test_cli.py -v` | verified 3/3 |
| `tests/integration/test_builder.py` | `pytest tests/integration/test_builder.py -v` | verified 3/3 |
| `tests/unit/test_linter.py` | `pytest tests/unit/test_linter.py -v` | verified 3/3 (depends on builder output) |

**Manual smoke test:**
```bash
cd /home/parallels/opm-ai
python -m opm_ai.cli build "5x5x3 depletion" -o /tmp/test.DATA
python -m opm_ai.cli lint /tmp/test.DATA   # -> "Passed"
```

---

## 9. Future Extensions

1. **Online LLM extraction** (Phase 2): function-calling schema -> `ModelSpec`; clarifying questions for ambiguous input.
2. **Template library**: register `scenario -> template.j2` mapping; 8-12 canonical cases from `IMPLEMENTATION_PLAN.md` section 8.
3. **Pre-process PVT builder** (Phase 2): correlations (Standing, Vasquez-Beggs) -> PVTO/PVTG blocks injected into template.
4. **Deck diff / round-trip**: parse existing deck -> `ModelSpec` -> regenerate -> semantic diff.
5. **CLI `chat` command**: stream `LLMClient.chat()` to terminal (previews Part 6 WebSocket).