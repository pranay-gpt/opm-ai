# OPM-AI Conversation Documentation Index

This directory contains the design records for all 9 parts of the OPM-AI workbench. Each document is a planning artifact (not code) that fixes decisions so a future coding session can implement without re-litigating architecture.

---

## **START HERE (after any context clear)**

1. **`STATUS.md`** - Living resume document (verified 2026-07-11). Current repo state, known defects in the v1 sketch, reconciled decisions, toolchain grounding, drift table. Read this FIRST after any context compaction or session boundary.
2. **`../../IMPLEMENTATION_PLAN.md`** - Staged build plan (Stage 0, 0.5, 1-7) with done-gates and TDD flow. References the spec docs below.

---

## Reading Order & One-Line Purpose

**START HERE:** `STATUS.md` is the living resume - read it first after any context clear or session start.

| File | Part | Module(s) | One-line Purpose |
|------|------|-----------|------------------|
| **STATUS.md** | - | - | **Living resume: current state, defects, drift table, session log** |
| **UI_DESIGN_SPEC.md** | - | `frontend/` | **Visual design extracted from Reference_UI.png: palette, components, 4 main views** |
| 00-overview-and-architecture.md | 0 | `opm_ai`, `settings` | AIM, architecture, stack decisions, Stage 0 foundation |
| 01-runner.md | 1 | `opm_ai.runner` | Wrap `/usr/bin/flow` as subprocess; structured `SimulationResult`, never raises |
| 02-linter.md | 2 | `opm_ai.linter` | Offline `Deck` parser + rule engine; `lint_deck` returns `LintResult` |
| 03-builder.md | 3 | `opm_ai.builder`, `opm_ai.llm`, `opm_ai.cli` | NL -> ModelSpec -> Jinja2 deck; auto-lint; LLM client; Click CLI |
| 04-preprocess.md | 4 | `opm_ai.preprocess` | PVT/relperm correlations to PROPS blocks; AI advisor; validators |
| 05-postprocess.md | 5 | `opm_ai.postprocess` | `resfo` summary -> KPIs -> Plotly; optional `rips` ResInsight 3D |
| 06-chat-and-api.md | 6 | `opm_ai.api`, `frontend/` | FastAPI backend exposing modules as `/api/*`; React+Vite SPA |
| 07-explainer.md | 7 | `opm_ai.explainer` | Deferred RAG explainer (chromadb/llama-index); Phase 3 |
| 08-deployment.md | 8 | `docker/`, `README.md`, CI | `docker compose up`; Dockerfile with Flow/ResInsight; GitHub Actions |

Cross-reference: `../../IMPLEMENTATION_PLAN.md` (staged build sequence), `../../BUILD_GUIDE.md` (API contracts).

---

## How to Use These Docs

1. Start with **STATUS.md** (the living resume) to understand current reality.
2. Then **00-overview-and-architecture.md** - it establishes the AIM, the two-process architecture, the hard API contract table (section 3), and the Stage 0 skeleton that every later part builds on.
2. Then read the parts in numeric order (01..08) as each one refines a single module and references its specific test contract.

---

## Contract Source of Truth

The hard API signatures that each part must implement are defined in **`BUILD_GUIDE.md` section 4** and are verbatim-asserted by the test files in `tests/unit/` and `tests/integration/`. Do not change a signature without updating its asserting test.

Key test-to-contract mappings (from 00-overview-and-architecture.md section 3):

| Part / Module | Signature | Asserting Test |
|---------------|-----------|----------------|
| Linter `linter.deck` | `Deck(deck_path: Path)` with `.sections`, `.get_section(name) -> str \| None` | `tests/unit/test_linter.py::test_parse_spe1_deck` |
| Linter `linter.linter` | `lint_deck(deck_path: Path) -> LintResult(.deck_path, .errors, .passed)` | `tests/unit/test_linter.py::test_lint_spe1_deck` |
| LLM `llm.client` | `LLMClient()` no-arg, `.chat(messages) -> str \| None`, `.available: bool` | `tests/unit/test_llm.py` |
| CLI `cli` | `main` click group; `--help` contains "OPM-AI"; `lint <deck>` prints "Passed"; `build "<desc>" -o <f>` prints "Lint passed" and writes file | `tests/unit/test_cli.py` |
| Builder `builder.extract` | `extract_parameters_offline(desc) -> ModelSpec(.scenario, .reservoir.nx/ny/nz, .wells[].well_type)` | `tests/integration/test_builder.py::test_extract_parameters_offline` |
| Builder `builder.builder` | `build_deck(desc, output_path=None) -> (deck_string, lint_result)`; deck has RUNSPEC/GRID/PROPS/SOLUTION/SCHEDULE; `lint_result.passed is True` | `tests/integration/test_builder.py::test_build_deck_depletion` |
| Runner `runner` | `SimulationJob(deck_path, output_dir, timeout)`; `run_simulation(job) -> SimulationResult(.success, .crash_report, .output_dir)`; never raises | `tests/integration/test_runner_spe1.py` |
| Postprocess `summary/kpi/plots` | `read_summary(dir) -> DataFrame` (has `TIME`, `WOPT:PROD`); `extract_kpis(df) -> dict` (has `days`>0); `plot_production/plot_pressure -> Figure` with exact trace counts | `tests/unit/test_plots.py`, `tests/integration/test_runner_spe1.py` |

---

## Consistency Notes

Cross-document contradictions, gaps, or drift found during review:

| Area | Docs Involved | Issue |
|------|---------------|-------|
| **ResInsight gRPC port** | 00-overview-and-architecture.md (line 193) says port **50051**; 05-postprocess.md (line 116) says port **50051** - consistent. |
| **OPM Flow thread flag** | 00-overview-and-architecture.md (line 117) and 01-runner.md (line 117) both state: OMIT `--threads` / `--enable-num-threads`; `flow 2026.04` only has `--threads-per-process`. Consistent. |
| **CLI framework** | 00-overview-and-architecture.md (line 97) and 03-builder.md (line 90) both specify **Click** (not Typer); `pyproject.toml` currently missing `click` dependency. Consistent decision, missing dep. |
| **UI framework** | 00-overview-and-architecture.md (D1), 03-builder.md, 06-chat-and-api.md, 08-deployment.md all agree: **React + Vite + TS** on FastAPI; `pyproject.toml` and `README.md` still reference `streamlit` (legacy). Consistent decision, drift in config files. |
| **LLM providers** | 00-overview-and-architecture.md (D4), 03-builder.md, 04-preprocess.md, 07-explainer.md all agree: **Groq (Llama-3.3-70B) + OpenAI-compatible (NVIDIA NIM)**; config-driven model IDs, offline fallback. Consistent. |
| **PVT correlation set** | 04-preprocess.md lists **Standing, Vasquez-Beggs, Al-Marhoun** for oil; **Corey, LET** for relperm. 02-linter.md rules reference these implicitly. No conflict. |
| **resfo usage** | 00-overview-and-architecture.md (D2), 01-runner.md, 05-postprocess.md all mandate **`resfo>=5.0`** for summary reading; `ecl2df`/`resdata` rejected. Consistent. |
| **RAG dependencies** | 00-overview-and-architecture.md (D3), 07-explainer.md both state: **deferred to Phase 3**; `chromadb`, `llama-index`, `sentence-transformers` NOT in `pyproject.toml` yet. Consistent. |
| **ResInsight service in compose** | 08-deployment.md uses `ghcr.io/opm/resinsight:2026.04` image; 05-postprocess.md and 00-overview-and-architecture.md assume local `/usr/bin/ResInsight` binary. Inconsistency: compose uses a container image while other docs assume host binary. Must reconcile at implementation. |
| **FastAPI port** | 00-overview-and-architecture.md, 03-builder.md, 06-chat-and-api.md, 08-deployment.md all specify **8000**. Consistent. Legacy `8555` (Streamlit) only appears as historical note in 08-deployment.md. |
| **Test gate for Runner** | 01-runner.md notes that `test_runner_spe1.py` imports `postprocess` (Phase 2) so it cannot pass in Phase 1; recommends a stub or `importorskip`. 00-overview-and-architecture.md mentions the same gate. Consistent. |
| **SPE1 fixture path** | All docs and tests reference `/home/parallels/opm-ai/tests/fixtures/spe1/SPE1CASE1.DATA` (absolute path). This is a repo-relative path in tests but absolute in docs; not portable. Should use a fixture or config-driven path in implementation. |
| **Python OPM bindings** | 00-overview-and-architecture.md (line 191), 01-runner.md (line 246) note: `opm.io` is in system `dist-packages`, may not be on venv path. Phase 1 avoids it (subprocess + text parser). Consistent intent, UNVERIFIED at implementation. |

**No other contradictions found.** The design decisions in 00-overview-and-architecture.md section 4 are consistently propagated through all sibling documents.