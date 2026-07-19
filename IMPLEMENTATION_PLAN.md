# OPM-AI Implementation Plan

Staged build plan. Companion to `BUILD_GUIDE.md` (architecture + API contract) and the
per-part design records in `docs/conversations/` (`00-08`).
UI is **React (Vite/TypeScript)** on a **FastAPI + Uvicorn** backend, not Streamlit.
Work top-down; each stage compiles and passes its named test before the next.

## Status and starting point (read this first)

Verified 2026-07-11. Full detail in `docs/conversations/STATUS.md` (the living resume
point; read it after any context clear).

- The repo is NOT greenfield. `opm_ai/` holds ~2036 lines of a reference-sketch
  implementation across all Phase-1 modules; all 33 tests currently pass.
- Those tests have weak assertions and miss real defects (built decks do not run in Flow
  because of a stray docstring in `base.j2`; the linter has no real severity model). See
  STATUS.md "Defects" for the list.
- Decision (2026-07-11): treat the existing code as a THROWAWAY REFERENCE SKETCH. Rewrite
  each module cleanly against its spec doc as we reach its stage. Salvage values and ideas
  from the sketch; do not assume it is correct. Tighten each test so it would have caught
  the sketch's defect.

## Conventions

- TDD against the contracts in `BUILD_GUIDE.md` section 4 and `docs/conversations/01-08`.
  Run `pytest` from `tests/` with the venv python (`.venv/bin/python -m pytest`).
- Commit per stage with working code. Never bypass hooks or disable tests.
- Each new module folder gets a short `context.md` (per CLAUDE.md folder rule).
- Verify before claiming done: run the relevant test file and paste output.
- A stage that rewrites a sketch module first deletes/replaces the sketch file, then
  rebuilds it to spec; it must not leave dead sketch code behind.

## Stage 0 - Repo skeleton (Phase 1)

- Ensure `opm_ai/` package has `__init__.py` files for every submodule in
  `BUILD_GUIDE.md` section 3 (`llm`, `builder`, `linter`, `runner`, `postprocess`,
  `preprocess`, `explainer`, `api`, `api/routes`). (Most exist in the sketch; create the
  missing `api/`, `preprocess/`, `explainer/`.)
- `opm_ai/settings.py` (rewrite): pydantic-settings loading `.env`. Pick ONE flow-path env
  name (`OPM_FLOW_BINARY`, matching `.env.example` and `00-overview`) and align settings +
  docs. Read every key the code uses from settings (no hardcoded `/usr/bin/flow`).
- `pip install -e .` succeeds; `import opm_ai` works so the `skipif` unit tests run.
- **Done when:** `pytest tests/unit/test_input_parser.py -v` passes (fixtures found,
  module importable).

## Stage 0.5 - Reconcile config + tighten tests (NEW, do before rewriting modules)

Purpose: make the toolchain honest so later stages have a trustworthy gate. Owns the drift
table in `STATUS.md`.

- `pyproject.toml`: drop `streamlit`; add `click`, `fastapi`, `uvicorn[standard]`. Re-run
  `pip install -e .` so the `opm-ai` console script actually installs.
- `pytest.ini`: fix the ignored `[tool:pytest]` header (rename to `[pytest]` or move to
  `pyproject [tool.pytest.ini_options]`); register markers `slow`/`integration`/`unit` so
  `--strict-markers` stops warning.
- Reconcile `.env.example` and `settings.py` key lists; document every key settings reads.
- Add the missing negative/round-trip tests that would have caught the sketch defects
  (a deck that SHOULD fail to lint; a built deck that must run in `flow --check`). These can
  start `xfail` and flip to pass as each module is rewritten.
- `git init` and make the first commit once the tree is clean (repo is currently not a git
  repo). Confirm `.env` is gitignored (it is).
- **Done when:** `pytest -q` runs with zero unknown-marker warnings and the new negative
  tests are collected (xfail allowed until the relevant module is rewritten).

## Stage 1 - Runner (Part 1)  [rewrite sketch to spec `01-runner.md`]

- `runner/models.py`: `SimulationJob(deck_path, output_dir, timeout)`,
  `SimulationResult(success, output_dir, crash_report, ...)`, `CrashReport`.
- `runner/runner.py`: `run_simulation(job)` - subprocess to `/usr/bin/flow`,
  **omit `--threads`**, timeout handling, parse stderr into `CrashReport`, locate
  `.SMSPEC/.UNRST`. Never raises; returns structured result.
- **Done when:** `pytest tests/integration/test_runner_spe1.py -v` passes
  (requires OPM Flow installed). `read_summary`/`extract_kpis` land in Stage 4;
  gate this test on those or mark accordingly.

## Stage 2 - Linter (Part 2)

- `linter/deck.py`: `Deck(deck_path)` - parse into sections; `.sections`,
  `.get_section(name)`. Offline, no LLM.
- `linter/linter.py`: `lint_deck(deck_path) -> LintResult(deck_path, errors, passed)`.
  Rule engine seeded from Eclipse keyword references in `tests/eclipse*/`. Optional
  LLM enhancement is additive and must degrade gracefully when offline.
- **Done when:** `pytest tests/unit/test_linter.py -v` passes (SPE1 clean, sample deck clean).

## Stage 3 - Builder + LLM + CLI (Part 3)

- `builder/models.py`: `ModelSpec` (`.scenario`, `.reservoir.nx/ny/nz`, `.wells[]`
  with `.well_type`), pydantic.
- `builder/extract.py`: `extract_parameters_offline(desc)` (regex/heuristic) + LLM path.
- `builder/templates/base.j2` + `builder/builder.py`: `build_deck(desc, output_path=None)
  -> (deck_string, lint_result)`; auto-lints; falls back to defaults when LLM absent.
- `llm/client.py`: `LLMClient()` with `.chat(messages)->str|None`, `.available: bool`
  (Groq/OpenAI, offline returns None).
- `cli.py`: click group `main` with `lint`, `build`, `run` (help contains "OPM-AI").
- **Done when:** `pytest tests/unit/test_llm.py tests/unit/test_cli.py
  tests/integration/test_builder.py -v` passes.
- **STATUS: COMPLETE (2026-07-18).** Roundtrip + dataset validation added:
  `tests/integration/test_builder_roundtrip.py` (flow dry-run + full run) and
  `tests/integration/test_dataset_validation.py` (9 scenarios lint+dry-run
  clean; 9 known-good fixtures not rejected by linter). Deck validation
  command is `flow --enable-dry-run=true --output-dir=DIR DECK` (bare
  `flow --check` is invalid in Flow 2026.04). LLM extraction path
  (`use_llm=True`) remains a Phase 2 stub by design.

## Stage 4 - Postprocess (Phase 2)

- `postprocess/summary.py`: `read_summary(output_dir) -> DataFrame` (via `resfo`;
  `TIME` + well vectors like `WOPT:PROD`).
- `postprocess/kpi.py`: `extract_kpis(df) -> dict` (includes `days`).
- `postprocess/plots.py`: `plot_production(df)` / `plot_pressure(df)` -> Plotly figs
  (trace counts per `BUILD_GUIDE.md` section 4).
- `postprocess/resinsight_bridge.py`: optional `rips` 3D snapshots.
- **Done when:** `pytest tests/unit/test_plots.py -v` passes and the Stage 1 SPE1
  integration test reads summary + KPIs end to end.
- **STATUS: COMPLETE (2026-07-19).**

## Stage 5 - FastAPI backend (Phase 2)

- `api/schemas.py`: request/response DTOs (build/lint/run/results/chat).
- `api/server.py`: `create_app()` - FastAPI instance, CORS for the Vite dev origin,
  optional static mount of the built frontend.
- `api/routes/*`: thin adapters calling `build_deck`, `lint_deck`, `run_simulation`,
  `read_summary`/`extract_kpis`, `LLMClient`. Long runs (`/api/run`) as background
  jobs with a status/poll endpoint; `/api/chat` streams via WebSocket or SSE.
  Serialize Plotly via `fig.to_json()`. No business logic in `api/`.
- Add `fastapi` + `uvicorn[standard]` to `pyproject.toml`; drop `streamlit`.
- **Done when:** `uvicorn opm_ai.api.server:create_app --factory` serves; add
  `tests/integration/test_api.py` (FastAPI `TestClient`) covering build/lint happy paths.
- **STATUS: COMPLETE (2026-07-19).**

## Stage 6 - React frontend (Phase 2)

- Scaffold `frontend/` (Vite + React + TS). `vite.config.ts` proxies `/api` to
  uvicorn (`:8000`).
- `src/api/client.ts`: typed fetch + WebSocket wrappers.
- Components per `BUILD_GUIDE.md` section 3: sidebar function selector, ChatPanel (streaming),
  DeckBuilder (syntax highlight), SimulationRunner, ResultsViewer (Plotly +
  ResInsight snapshots), LinterPanel, SettingsPanel (keys/provider), Dark Void theme.
- **Done when:** `npm run build` succeeds; dev flow (`uvicorn` + `npm run dev`) runs a
  full build -> lint -> run -> results loop against a fixture.
- **STATUS: COMPLETE (2026-07-19).**

## Stage 7 - Preprocess + Deployment (Phase 2 tail / Part 8)

- `preprocess/pvt_builder.py`: Standing / Vasquez-Beggs / Al-Marhoun + Corey/LET,
  emit PVTO/PVDG/SWOF/SGOF blocks.
- `docker/`: Dockerfile (Ubuntu + OPM PPA + `flow`/ResInsight + pip deps + Node build
  of `frontend/`) and `docker-compose.yml` (backend service + built frontend; env keys).
- Update `README.md` quick-start: backend (`uvicorn`) + frontend (`npm run dev` / build)
  instead of `streamlit run`.
- GitHub Actions CI: `pytest` (SPE1) + `npm run build`.
- **STATUS: COMPLETE (2026-07-19).**

## Phase 3 - Explainer / RAG (deferred)

RAG (LlamaIndex/LangChain + chromadb) over the Eclipse keyword references and
`tests/fixtures` deck comments. Add those deps only at this stage.

## Claude Code Tooling (per-stage)

Recommendations from the `claude-automation-recommender` skill, mapped to the stage
where each pays off. These are optional developer-experience aids, not build deliverables.

| Tooling | Type | Supports stage | Purpose |
|---------|------|----------------|---------|
| **context7** | MCP | All | Live docs for FastAPI, React, pydantic, plotly, Groq/OpenAI SDKs (reduces hallucinated APIs). Niche OPM/`resfo`/`rips` have no MCP; use bindings + local binaries. |
| **`project-conventions`** skill (Claude-only) | Skill | Stage 0 | Encode CLAUDE.md rules (no em-dash/emoji, verify APIs, per-folder `context.md`, incremental commits) as auto-applied background knowledge. |
| **`contract-check`** skill (user-only) | Skill | Stage 0+ | One command that runs the pytest target for a given stage and reports pass/fail. |
| **`.env` block** hook (PreToolUse) | Hook | Stage 0 | Protect real API-key files from accidental writes. |
| **pytest-on-edit** hook (PostToolUse) | Hook | Stages 1-4 | Run the affected contract test on save to keep stages green. |
| **`new-module`** skill (user-only) | Skill | Stages 1-4 | Scaffold an `opm_ai` submodule with `__init__.py` + `context.md` + placeholder test. |
| **Playwright** | MCP | Stage 6 | Drive the running React SPA, screenshot panels, validate build->lint->run->results loop. |
| **`frontend-design`** plugin | Skill | Stage 6 | Polished React components matching the Dark Void theme intent. |
| **`new-component`** skill (user-only) | Skill | Stage 6 | Scaffold React component + test + story from templates. |
| **Memory** | MCP | All | Persist decisions (React/FastAPI, API contract) across sessions. |
| **Docker MCP** | MCP | Stage 7 | Enable once `docker/` exists. |
| **GitHub MCP** + **`commit`** plugin | MCP + Skill | Stage 7 / release | Enable once a GitHub remote is added (none yet). |

Setup notes: check MCP servers into a repo `.mcp.json` for team sharing; custom skills
live in `.claude/skills/<name>/SKILL.md`; hooks in `.claude/settings.json`. Implementing
these is deferred - this table is the reference for when each becomes relevant.

## Open items to confirm before/while building

- Backend framework **FastAPI** and frontend tooling **Vite + TS** are defaults chosen
  here; change Stages 5-6 if a different stack is preferred.
- Long-running `/api/run`: background task + polling assumed (vs. blocking request).
