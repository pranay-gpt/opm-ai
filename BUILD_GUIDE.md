# OPM-AI Build Guide

> **STATUS 2026-07-22: BUILD COMPLETE.** Everything specified here is implemented
> and shipped (see CONTEXT.md for current state, FORWARD_PLAN.md for remaining
> planned capabilities). This file is the original architecture spec, kept as the
> contract reference; where it says "currently empty" or "to build", read it as
> the historical starting point, not the present.

Source-of-truth for building the project. Distilled from `Instructions.txt` (GUIDE 1-4)
and the concrete API contract encoded in `tests/`. The package `opm_ai/` is currently
empty; this document is the spec for what to build.

## 1. AIM (verbatim)

> "To create an AI layer on top of open source reservoir simulators that will help
> academic students, researchers and faculty to understand and teach reservoir
> simulation in the most efficient and fun way using simple chats. There will be pre
> and post processing layers/workflow. It should be open source and useable by anyone
> using GitHub."

Engineering restatement: a Python-native, open-source workbench that wraps **OPM Flow**
(physics), **ResInsight** (visualisation) and **LLM APIs** (intelligence) into a single
chat-driven educational tool. A user types plain English; the system builds, runs,
visualises and explains a reservoir simulation. No license, no SLB login, one
`docker compose up`.

## 2. Ground truth vs. aspiration (resolve conflicts here)

Authoritative decisions for this build:

- **UI framework: React** (per user directive, matching `Instructions.txt` GUIDE 1),
  **not** Streamlit. React runs in the browser and cannot import the Python modules
  directly, so the app is split into two processes:
  - **Backend API: FastAPI + Uvicorn** — exposes the `opm_ai` modules (build, lint,
    run, results, chat) as REST + WebSocket/SSE endpoints. Chosen over Flask for
    native async, pydantic-native request/response models (we already depend on
    pydantic), and first-class streaming for LLM chat responses.
  - **Frontend: React + Vite + TypeScript** — the SPA in `frontend/` calls the
    FastAPI backend. Vite chosen over Next.js/CRA (no SSR needed; fast dev server).
- **Deck output reader: `resfo`** (not `resdata`/`ecl2df`).
- **RAG stack (langchain/chromadb) is NOT a dependency** yet. The explainer (Part 7)
  is deferred; do not add those deps until that phase.
- LLM providers: **Groq + OpenAI** (NVIDIA NIM via OpenAI-compatible endpoint).

Follow-up needed when implementing (currently still reference Streamlit):
`pyproject.toml` (drop `streamlit`, add `fastapi` + `uvicorn[standard]`) and
`README.md` (replace the `streamlit run ...` quick-start with backend + frontend
run commands). The `opm_ai.cli:main` console script is unaffected.

## 3. Target package layout

Derived from the exact import paths the tests use. Create these modules:

```
opm_ai/
├── __init__.py
├── cli.py                    # click group `main`: lint / build / run
├── settings.py               # dotenv/pydantic-settings config (API keys, flow path)
├── llm/
│   ├── __init__.py
│   └── client.py             # LLMClient (Groq/OpenAI, offline fallback)
├── builder/
│   ├── __init__.py
│   ├── builder.py            # build_deck()
│   ├── extract.py            # extract_parameters_offline() + LLM extraction
│   ├── models.py             # ModelSpec, Reservoir, WellSpec (pydantic)
│   └── templates/base.j2     # Jinja2 deck templates
├── linter/
│   ├── __init__.py
│   ├── deck.py               # Deck parser (sections)
│   └── linter.py             # lint_deck() + rule engine
├── runner/
│   ├── __init__.py
│   ├── models.py             # SimulationJob, SimulationResult, CrashReport
│   └── runner.py             # run_simulation()
├── postprocess/
│   ├── __init__.py
│   ├── summary.py            # read_summary()
│   ├── kpi.py                # extract_kpis()
│   ├── plots.py              # plot_production(), plot_pressure()
│   └── resinsight_bridge.py  # rips API (optional, later)
├── preprocess/
│   └── pvt_builder.py        # PVT/relperm correlations (Part 4, later)
├── explainer/                # RAG (Part 7, deferred)
└── api/
    ├── __init__.py
    ├── server.py             # FastAPI app factory (create_app), CORS, static mount
    ├── schemas.py            # request/response pydantic models (API DTOs)
    └── routes/
        ├── __init__.py
        ├── build.py          # POST /api/build  -> deck + lint result
        ├── lint.py           # POST /api/lint   -> LintResult
        ├── run.py            # POST /api/run    -> SimulationResult (async job)
        ├── results.py        # GET  /api/results/{id} -> KPIs + plot JSON
        └── chat.py           # WS/SSE /api/chat  -> streaming LLM router

frontend/                     # React SPA (Vite + TypeScript), calls the FastAPI backend
├── package.json
├── vite.config.ts            # dev proxy /api -> uvicorn (default :8000)
├── index.html
├── tsconfig.json
└── src/
    ├── main.tsx
    ├── App.tsx               # sidebar function selector (Chat/Builder/Run/Results/Settings)
    ├── api/client.ts         # typed fetch + WebSocket wrappers to /api/*
    ├── theme.ts              # Dark Void theme etc.
    └── components/
        ├── ChatPanel.tsx     # streaming chat interface
        ├── DeckBuilder.tsx   # NL -> deck, syntax highlighting
        ├── SimulationRunner.tsx
        ├── ResultsViewer.tsx # Plotly charts + ResInsight snapshots
        ├── LinterPanel.tsx
        └── SettingsPanel.tsx # API keys, provider selection
```

The FastAPI backend is a thin adapter: routes validate input with `schemas.py`,
call the existing `opm_ai` module functions (`build_deck`, `lint_deck`,
`run_simulation`, `read_summary`/`extract_kpis`, `LLMClient`), and serialize results
to JSON (Plotly figures via `fig.to_json()`). No business logic lives in `api/`.

## 4. API contract (extracted from tests) — build to these signatures

These are hard requirements. Each row is asserted by a test file.

### linter (`tests/unit/test_linter.py`)
- `Deck(deck_path: Path)` — attribute `.sections` (non-empty for SPE1);
  `.get_section("RUNSPEC")` / `get_section("GRID")` return non-`None`.
- `lint_deck(deck_path: Path) -> LintResult` where `LintResult` has:
  - `.deck_path: str` (equals `str(deck_path)`)
  - `.errors: list` (empty for valid SPE1 deck and minimal sample deck)
  - `.passed: bool` (True when no errors)

### llm (`tests/unit/test_llm.py`)
- `LLMClient()` constructs with no args, never raising.
- `.chat(messages: list[dict]) -> str | None` — returns `None` when offline (no API key).
- `.available: bool`.

### cli (`tests/unit/test_cli.py`)
- `main` is a `click` command group. `--help` output contains `"OPM-AI"`.
- `main lint <deck>` exits 0, prints `"Passed"` for SPE1.
- `main build "<desc>" -o <file>` exits 0, writes `<file>`, prints `"Lint passed"`.
- (`main run <deck>` per README.)

### builder (`tests/integration/test_builder.py`)
- `extract_parameters_offline(desc: str) -> ModelSpec` where ModelSpec has:
  - `.scenario` (e.g. `"depletion"`)
  - `.reservoir.nx / .ny / .nz` (ints parsed from `"10x10x5"`)
  - `.wells: list`; `wells[0].well_type` (e.g. `"PROD"`)
- `build_deck(desc: str, output_path: Path | None = None) -> (deck_string: str, lint_result)`
  - `deck_string` contains sections: RUNSPEC, GRID, PROPS, SOLUTION, SCHEDULE
  - `lint_result.passed is True`, `lint_result.errors == []`
  - when `output_path` given, file is written.

### runner (`tests/integration/test_runner_spe1.py`)
- `SimulationJob(deck_path=Path, output_dir=Path, timeout=int)` (pydantic/dataclass).
- `run_simulation(job) -> SimulationResult` with `.success: bool`,
  `.crash_report`, `.output_dir: Path`. Never raises (returns structured errors).

### postprocess
- `read_summary(output_dir: Path) -> pandas.DataFrame` — has `"TIME"` column and
  well vectors like `"WOPT:PROD"` (`tests/integration/test_runner_spe1.py`).
- `extract_kpis(df) -> dict` — includes `"days"` key (> 0), plus field KPIs.
- `plot_production(df) -> plotly Figure` — one trace per FOPR/FWPR/FGPR present;
  empty DataFrame yields `len(fig.data) == 0` (`tests/unit/test_plots.py`).
- `plot_pressure(df) -> plotly Figure` — one trace per `WBHP:*` column.

## 5. Test inventory

| File | Type | Asserts |
|------|------|---------|
| `unit/test_input_parser.py` | unit | fixtures exist; SPE1 `.DATA` present; skips deck-parse tests if `opm_ai` missing |
| `unit/test_keyword_processing.py` | unit | regex keyword matching, case-insensitivity, fixture access |
| `unit/test_linter.py` | unit | `Deck` parse + `lint_deck` contract above |
| `unit/test_llm.py` | unit | `LLMClient` contract |
| `unit/test_cli.py` | unit | click CLI lint/build |
| `unit/test_plots.py` | unit | Plotly trace counts |
| `integration/test_builder.py` | integ | offline extract + `build_deck` |
| `integration/test_simulation_runner.py` | integ | fixture-structure checks (many stubs) |
| `integration/test_runner_spe1.py` | integ (slow) | end-to-end Flow run of SPE1 + KPIs |

Markers (`pytest.ini`): `slow`, `integration`, `unit`. `testpaths = .`, run from `tests/`.
`conftest.py` provides `temp_dir` and `sample_opm_input` fixtures.

Note: unit tests are written to pass **before** implementation (they `skipif` on missing
`opm_ai`, or only test regex/fixtures). The linter/llm/cli/plots/builder tests are the
real TDD targets. `test_runner_spe1` requires OPM Flow installed.

## 6. Fixtures

`tests/fixtures/` holds **110 reference deck directories** (a clone of OPM `opm-tests`):
`spe1`, `spe10`, `polymer`, `norne`, `drogon`, `co2store`, `h2store`, `aquifers`,
`gaslift`, `msw`, `pyaction`, etc. Key one for TDD:
`tests/fixtures/spe1/SPE1CASE1.DATA` (FIELD units, OIL/GAS/WATER/DISGAS black-oil,
10x10x3, injector+producer) with precomputed `.ESMRY/.UNRST/.EGRID/.SMSPEC` outputs.

Eclipse keyword reference HTML lives in `tests/eclipse/` and
`tests/eclipse_fileformat/` — seed material for the linter rule set and (later) the
RAG knowledge base.

## 7. Installed toolchain (from GUIDE 4 / OPM.md)

- `flow` at `/usr/bin/flow` — **version 2026.04**, Ubuntu 24.04, Open MPI 4.1.6.
- Python bindings: `/usr/lib/python3/dist-packages/opm/` (`opm.io` parser +
  binary readers, `opm.simulators.BlackOilSimulator`).
- `ResInsight` at `/usr/bin/ResInsight`; gRPC on port 50051; drive via `rips`.
- Reference decks (system): `~/opm/opm-tests/`.
- Editor/linter seed rules: `opm-flow-editor-support` VS Code extension `scripts/`.

Daily-use imports: `opm.io` (parse), `opm.simulators` (run), `rips` (visualise).
Runner note from GUIDE 1: omit the `--threads` flag due to compatibility issues.

## 8. Build order

**Phase 1 (v1):**
1. Repo skeleton + package `__init__` files + `settings.py`.
2. **Runner** (Part 1) — prove `flow SPE1CASE1.DATA` works, structured results.
3. **Linter** (Part 2) — `Deck` parser + rule engine (offline, no LLM required).
4. **Builder** (Part 3) — `ModelSpec` + Jinja2 templates + `build_deck` (auto-lints).
5. **LLM client** + **CLI** wiring; README/demo.

**Phase 2 (v1.1):** Postprocess (`read_summary`/`extract_kpis`/plots), ResInsight
bridge, then the web app in two steps: (a) **FastAPI backend** exposing the modules
as `/api/*` endpoints, (b) **React (Vite/TS) frontend** consuming them; preprocess PVT.

**Phase 3 (v1.2):** Educational explainer / RAG.

## 9. Working rules (from CLAUDE.md)

- Read existing files before writing; verify APIs, never guess.
- Incremental commits that compile and pass tests; TDD where a test exists.
- Break work into 3-6 stages in `IMPLEMENTATION_PLAN.md` per phase.
- Linter must work offline (rule engine only); runner must never raise;
  builder must fall back to defaults when the LLM is unavailable.
- Maintain a per-folder context `.md` inside each new module directory.
