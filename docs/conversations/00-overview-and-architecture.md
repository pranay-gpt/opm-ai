# Overview and Architecture  (module: `opm_ai` root + `opm_ai.settings`)

> The entry-point design record for OPM-AI and the Stage 0 foundation decision log.
> Read this first; every sibling doc (01 to 08) refines one Part described here.

This is a planning artifact, not code. It fixes the decisions a future coding
session needs so it can start building without re-litigating architecture.
Grounded in `BUILD_GUIDE.md`, `IMPLEMENTATION_PLAN.md`, `Instructions.txt`
(GUIDE 1 to 4), `OPM.md`, and the `tests/` contract. Claims that cannot be
verified from those sources are marked UNVERIFIED with a check-at-implementation note.

---

## 1. Role in the AIM

AIM (verbatim):

> "To create an AI layer on top of open source reservoir simulators that will
> help academic students, researchers and faculty to understand and teach
> reservoir simulation in the most efficient and fun way using simple chats.
> There will be pre and post processing layers/workflow. It should be open
> source and useable by anyone using GitHub."

Engineering restatement: a Python-native, open-source, chat-driven educational
workbench that wraps three engines behind one plain-English interface.

- OPM Flow (physics): the black-oil / thermal / CO2 simulator at `/usr/bin/flow`.
- ResInsight (visualisation): driven headless via the `rips` gRPC client.
- LLM APIs (intelligence): Groq and OpenAI-compatible (NVIDIA NIM) for NL parsing
  and explanation.

A user types plain English; the system builds, runs, visualises and explains a
reservoir simulation. No commercial license, no SLB login, one `docker compose up`.

Users and why chat-first lowers the barrier:

| User | Today's barrier | What chat-first removes |
|------|-----------------|-------------------------|
| Students | Eclipse deck syntax (RUNSPEC/GRID/PROPS/SCHEDULE, `/` terminators, keyword order) is opaque before any physics is learned | They describe intent ("10x10x3, one injector one producer, 5-year waterflood") and read a valid, linted deck back |
| Researchers | Setup and tooling friction (licenses, file formats, plumbing) dwarfs the actual experiment | One command brings up a working build to run to results loop on reference decks |
| Faculty | Live classroom demos need a preinstalled commercial stack | Open-source stack, reproducible container, explainable outputs for teaching |

Chat-first is the pedagogy: the deck, the run, and the KPIs stay visible, so the
tool teaches the syntax instead of hiding it. The linter gives immediate,
rule-based feedback so learning does not depend on an API key being present.

---

## 2. Position in build order  (phase; depends-on; depended-on-by)

This doc is the Stage 0 record. Depends-on: nothing. Depended-on-by: every Part.

Build order is dependency-driven: prove simulation, then validate, then generate.
Runner first (can we run Flow at all and capture structured results), Linter next
(can we judge a deck offline), Builder last in Phase 1 (generate a deck, then
auto-lint it). Part 8 (Deployment) is scaffolded first as an empty skeleton and
finished at the end of each phase.

| Phase | Version | Part | Module(s) | Sibling doc | Rationale |
|-------|---------|------|-----------|-------------|-----------|
| 1 | v1 | Stage 0 skeleton + settings | `opm_ai/`, `opm_ai.settings` | this doc | House first: package importable, config loads, tests can run |
| 1 | v1 | Part 1 Runner | `opm_ai.runner` | 01-runner.md | Prove simulation: `flow SPE1CASE1.DATA` to structured result |
| 1 | v1 | Part 2 Linter | `opm_ai.linter` | 02-linter.md | Validate offline: rule engine, no LLM, encodes domain expertise |
| 1 | v1 | Part 3 Builder + LLM + CLI | `opm_ai.builder`, `opm_ai.llm`, `opm_ai.cli` | 03-builder.md | Generate: NL to deck, auto-lint, degrade to defaults offline |
| 2 | v1.1 | Part 5 Postprocess + ResInsight | `opm_ai.postprocess` | 05-postprocess.md | Read summary to KPIs to Plotly; `rips` 3D snapshots |
| 2 | v1.1 | Part 6 API then Frontend | `opm_ai.api`, `frontend/` | 06-chat-and-api.md | Expose modules as REST/WS, then React SPA consumes them |
| 2 | v1.1 | Part 4 Preprocess PVT | `opm_ai.preprocess` | 04-preprocess.md | PVT/relperm correlations feed the builder's PROPS section |
| 3 | v1.2 | Part 7 Explainer / RAG | `opm_ai.explainer` | 07-explainer.md | Educational RAG; adds chromadb/llama-index deps only here |
| 1-3 | all | Part 8 Deployment | `docker/`, `README.md`, CI | 08-deployment.md | Skeleton first, finished at the tail of each phase |

Dependency nuance: the Runner's full end-to-end test (`test_runner_spe1.py`) also
imports `read_summary`/`extract_kpis` from `postprocess` (Phase 2). So the Runner
lands in Phase 1 but its slow SPE1 test is gated until Postprocess exists, per
`IMPLEMENTATION_PLAN.md` Stage 1 "Done when" note. The Builder depends on the
Linter (it auto-lints), which is why Linter precedes Builder inside Phase 1.

---

## 3. Hard API contract

Stage 0's own contract is minimal and asserted by `tests/unit/test_input_parser.py`:

- `import opm_ai` succeeds (the test `skipif`s the parse cases when it does not).
- `tests/fixtures/` exists with per-scenario dirs; `spe1/SPE1CASE1.DATA` present.
- Editable install (`pip install -e .`) makes `opm_ai` importable so downstream
  contract tests can run.

The full cross-module contract lives in `BUILD_GUIDE.md` section 4 and is
verbatim-asserted by the test files below. Each row is the hard target for one
sibling doc; do not change a signature without changing its test.

| Part / module | Signature (from tests) | Asserting test |
|---------------|------------------------|----------------|
| Linter `linter.deck` | `Deck(deck_path: Path)` with `.sections`, `.get_section(name) -> section \| None` | `unit/test_linter.py` |
| Linter `linter.linter` | `lint_deck(deck_path: Path) -> LintResult(.deck_path: str, .errors: list, .passed: bool)` | `unit/test_linter.py` |
| LLM `llm.client` | `LLMClient()` no-arg, `.chat(messages: list[dict]) -> str \| None`, `.available: bool` | `unit/test_llm.py` |
| CLI `cli` | `main` click group; `--help` contains `"OPM-AI"`; `lint <deck>` prints `"Passed"`; `build "<desc>" -o <f>` prints `"Lint passed"` and writes `<f>` | `unit/test_cli.py` |
| Builder `builder.extract` | `extract_parameters_offline(desc) -> ModelSpec(.scenario, .reservoir.nx/ny/nz, .wells[].well_type)` | `integration/test_builder.py` |
| Builder `builder.builder` | `build_deck(desc, output_path=None) -> (deck_string, lint_result)`; string has RUNSPEC/GRID/PROPS/SOLUTION/SCHEDULE; `lint_result.passed is True` | `integration/test_builder.py` |
| Runner `runner` | `SimulationJob(deck_path, output_dir, timeout)`; `run_simulation(job) -> SimulationResult(.success, .crash_report, .output_dir)`; never raises | `integration/test_runner_spe1.py` |
| Postprocess `postprocess.summary/kpi/plots` | `read_summary(dir) -> DataFrame` (has `TIME`, `WOPT:PROD`); `extract_kpis(df) -> dict` (has `days`>0); `plot_production`/`plot_pressure -> Figure` with exact trace counts | `unit/test_plots.py`, `integration/test_runner_spe1.py` |

Note the offline-friendliness baked into the contract: `LLMClient.chat` may return
`None`, and the plots/linter/builder tests never require an API key.

---

## 4. Key design decisions

### Architecture: the two-process split (text diagram)

React runs in the browser and cannot import the Python modules, so the app is two
processes. The FastAPI backend is a thin adapter: routes validate with
`api/schemas.py`, call the existing module functions, and serialize (Plotly via
`fig.to_json()`). No business logic lives in `api/`.

```
Process A: Browser                Process B: Python (uvicorn)                    External engines
------------------                ---------------------------                    ----------------
frontend/ (React+Vite+TS)         opm_ai.api (FastAPI+Uvicorn)
  App.tsx  sidebar selector  --->   routes/build.py  --> opm_ai.builder  ------> opm_ai.llm --HTTPS--> Groq / OpenAI-NIM
  ChatPanel.tsx              WS/SSE  routes/lint.py   --> opm_ai.linter          (rule engine, offline-safe)
  DeckBuilder.tsx            <--->   routes/run.py    --> opm_ai.runner  --subprocess--> /usr/bin/flow (2026.04)
  SimulationRunner.tsx      HTTP     routes/results.py--> opm_ai.postprocess -> resfo (.ESMRY/.UNSMRY)
  ResultsViewer.tsx         /api/*   routes/chat.py   --> opm_ai.llm             opm_ai.postprocess.resinsight_bridge
  LinterPanel.tsx                                     --> opm_ai.preprocess         --gRPC :50051--> /usr/bin/ResInsight (rips)
  SettingsPanel.tsx                  server.py create_app(): CORS, static mount
```

Mapping the 8 Parts to the module layout (`BUILD_GUIDE.md` section 3):

| Part | Name | Module(s) | Key files |
|------|------|-----------|-----------|
| 1 | OPM Engine Wrapper | `opm_ai.runner` | `runner.py`, `models.py` |
| 2 | AI Deck Linter | `opm_ai.linter` | `deck.py`, `linter.py` |
| 3 | Description-to-Deck Builder | `opm_ai.builder` (+ `opm_ai.llm`, `opm_ai.cli`) | `builder.py`, `extract.py`, `models.py`, `templates/base.j2` |
| 4 | Pre-Processing (PVT) | `opm_ai.preprocess` | `pvt_builder.py` |
| 5 | Post-Processing + ResInsight | `opm_ai.postprocess` | `summary.py`, `kpi.py`, `plots.py`, `resinsight_bridge.py` |
| 6 | Conversational / Web layer | `opm_ai.api` + `frontend/` | `server.py`, `schemas.py`, `routes/*`, `src/*` |
| 7 | Educational Explainer / RAG | `opm_ai.explainer` | (deferred, Phase 3) |
| 8 | Deployment / Packaging | `docker/`, `README.md`, CI | Dockerfile, compose, Actions |

### Authoritative stack decisions (resolve older-guide conflicts here)

| # | Decision | Chosen | Rejected | Conflict it resolves |
|---|----------|--------|----------|----------------------|
| D1 | UI + backend | React+Vite+TS SPA on FastAPI+Uvicorn | Streamlit | `pyproject.toml` and `README.md` still say Streamlit; older GUIDE 1 module `opm_ai.chat` |
| D2 | Deck output reader | `resfo` (>=5.0) | `resdata`, `ecl2df` | GUIDE 1/GUIDE 4 mention `ecl2df`/`resdata` |
| D3 | RAG stack | deferred to Phase 3 | langchain/chromadb/llama-index now | Instructions list them as deps up front |
| D4 | LLM providers | Groq (Llama-3.3-70B-versatile) + OpenAI-compatible (NVIDIA NIM via `base_url`) | single-provider hardcode | GUIDE 4 lists many providers |
| D5 | Backend web framework | FastAPI | Flask | native async, pydantic-native DTOs, streaming for chat |

Expanded rationale for the load-bearing ones:

- D1 Decision: two-process React + FastAPI. Rationale: React cannot import Python;
  FastAPI gives async + pydantic DTOs (already a dependency) + first-class SSE/WS
  streaming for LLM chat. Alternatives: Streamlit (single process, simplest, but
  couples UI to Python and blocks on long runs); Next.js (SSR not needed).
  Consequences: a network boundary and DTO layer (`api/schemas.py`) must be built;
  CORS and a dev proxy (`vite.config.ts` /api to :8000) are required. Streamlit
  references in `pyproject.toml` and `README.md` must be removed (see section 6).
- D2 Decision: `resfo` for summary/restart reads. Rationale: it is the reader named
  authoritative in `BUILD_GUIDE.md`; already pinned `resfo>=5.0` in `pyproject.toml`.
  Alternatives: `ecl2df` (gives a summary DataFrame directly but is an extra heavy
  dep and not the chosen path), `resdata`. Consequences: `read_summary` must
  assemble the labeled DataFrame itself from the SMSPEC metadata plus UNSMRY/ESMRY
  values; `resfo` is a low-level array reader, not a summary-to-DataFrame helper
  (UNVERIFIED exact API, see section 5).
- D3 Decision: no RAG deps until Phase 3. Rationale: keep the Phase 1 install small
  and offline-testable. Consequences: `opm_ai/explainer/` stays an empty package;
  do not add chromadb/llama-index/langchain/tavily to `pyproject.toml` before then.

### Cross-cutting invariants (every Part must honour)

| Invariant | Where enforced | Why |
|-----------|----------------|-----|
| Linter works fully offline (rule engine only; LLM is additive) | `linter.lint_deck` | Teaching feedback must not depend on an API key |
| Runner never raises; returns a structured `SimulationResult`/`CrashReport` | `runner.run_simulation` | A crashed sim is a normal outcome to display, not an exception |
| Builder falls back to defaults when the LLM is absent | `builder.build_deck` via `extract_parameters_offline` | `build_deck` and the CLI build test run with no key |
| Tests pass offline (no API key in CI) | all contract tests | CI on GitHub Actions has no secret key; `LLMClient` returns `None` |

---

## 5. Toolchain grounding

Verified from `OPM.md`, `BUILD_GUIDE.md` section 7, and `Instructions.txt` GUIDE 4.

| Component | Path / endpoint | Version | Used by | Notes |
|-----------|-----------------|---------|---------|-------|
| OPM Flow | `/usr/bin/flow` | 2026.04 | Runner (subprocess) | `flow CASE.DATA --output-dir=OUT`; omit `--threads` (compat); exit 0 ok, 1 handled error, 134 assert-abort |
| OPM Python bindings | `/usr/lib/python3/dist-packages/opm/` | 2026.04 | optional | `opm.io` (Parser, EclFile, Schedule, EclipseGrid, SummaryState); `opm.simulators.BlackOilSimulator` |
| resfo | pip, `resfo>=5.0` | pinned | Postprocess | reader for `.ESMRY`/`.UNSMRY`/`.SMSPEC` arrays |
| ResInsight | `/usr/bin/ResInsight`, gRPC :50051 | see UNVERIFIED | Postprocess bridge | driven by `rips`; launch with server enabled |
| rips | pip, unpinned in `pyproject.toml` | UNVERIFIED | Postprocess bridge | `Instance.launch()/find()`, `loadCase`, `exportSnapshots` (from GUIDE 4) |
| Reference decks | `tests/fixtures/` (clone of opm-tests) | 110 dirs | all tests | canonical: `spe1/SPE1CASE1.DATA` |
| Companion CLIs | with `flow` | 2026.04 | optional | `summary`, `compareECL`, `convertECL`, `rst_deck`, `opmpack`, `co2brinepvt` |

Runner grounding (from `OPM.md` section 7, tested on this host):
- `flow --enable-dry-run=true CASE.DATA` is a fast parse+config validation mode.
- `mpirun -np N` needs `N <= nproc` or add `--oversubscribe`.
- Real diagnostics live in `CASE.PRT` (human) and `CASE.DBG` in `--output-dir`;
  surface these on failure.

UNVERIFIED items and what to check at implementation time:

- `read_summary` exact `resfo` calls: `resfo` reads raw keyword arrays; the mapping
  to a pandas DataFrame with `TIME` and labeled well vectors (`WOPT:PROD`) from
  SMSPEC (`KEYWORDS`/`WGNAMES`/`UNITS`) + UNSMRY/ESMRY (`PARAMS`) must be written.
  Check the `resfo>=5.0` API for how it returns array records before coding.
- ResInsight and `rips` versions: `OPM.md` does not capture the installed
  ResInsight version; GUIDE 2 says ResInsight >= 2025.04. `rips` is unpinned in
  `pyproject.toml`. Verify `rips` matches the installed ResInsight and pin it.
- Groq model id `llama-3.3-70b-versatile` and NVIDIA NIM `base_url`: provider model
  ids change; keep them config-driven via settings, do not hardcode. Verify the
  current Groq model id at implementation.
- `opm.io` visibility inside the project `.venv`: system `dist-packages` may not be
  on the venv path. Phase 1 avoids this by using subprocess to `/usr/bin/flow` and a
  lightweight text `Deck` parser (not `opm.io`). Confirm before relying on `opm.io`.

---

## 6. Implementation approach  (Stage 0)

### Current repo state (verified)

- SUPERSEDED (2026-07-11): the "empty package" note below was true when this doc was
  written but is now stale. `opm_ai/` contains a throwaway reference-sketch
  implementation (~2036 lines, all 33 tests pass but with defects the tests miss). The
  authoritative, up-to-date state and reconciliation live in `STATUS.md`. Read that
  first. The design content in the rest of this doc remains the spec to build toward.
- (Historical) `opm_ai/` package is EMPTY (greenfield); no `__init__.py` yet.
- `tests/` exists and encodes the API contract; `tests/fixtures/` has 110 reference
  deck dirs (clone of OPM opm-tests). `pytest.ini`: `testpaths = .`, run from `tests/`,
  markers `slow`/`integration`/`unit`; `conftest.py` gives `temp_dir` and
  `sample_opm_input` fixtures.
- Git is NOT initialised. A `.git/` directory exists but is empty (only `.` and
  `..`), so `git status` reports "not a git repository". No remote.
- `pyproject.toml` drift: lists `streamlit>=1.58`; does NOT list `click`
  (CLI tests do `from click.testing import CliRunner`), `fastapi`, or
  `uvicorn`. Correctly pins `resfo>=5.0`, `pydantic-settings`, `groq`, `openai`,
  `jinja2`, `pandas`, `plotly`, `loguru`, `python-dotenv`; `rips` is unpinned.
  `pytest` is under the `dev` extra.
- `README.md` quick-start still says `streamlit run opm_ai/app/streamlit_app.py`.
- `.env` exists and `.env.example` documents keys; `.gitignore` already ignores
  `.env` (good, keeps keys out of the first commit).

### Concrete cleanup actions this implies

1. `git init` (populate the empty `.git/`); no remote is required yet (the no-arg
   `ultrareview`/local-branch flows work without a GitHub remote).
2. `pyproject.toml`: drop `streamlit`; add `click`, `fastapi`, `uvicorn[standard]`;
   pin `rips` to the installed ResInsight's client. Keep RAG deps out until Phase 3.
3. `README.md`: replace the `streamlit run ...` quick-start with backend
   (`uvicorn opm_ai.api.server:create_app --factory`) + frontend (`npm run dev`).
4. Create the `opm_ai/` package skeleton and `__init__.py` files (below).
5. Add `opm_ai/settings.py` and confirm `.env` is loaded but never committed.

### Ordered Stage 0 steps and files to create

1. Package skeleton with `__init__.py` for every submodule from `BUILD_GUIDE.md`
   section 3: `opm_ai/__init__.py`, then `llm/`, `builder/` (+ `templates/`),
   `linter/`, `runner/`, `postprocess/`, `preprocess/`, `explainer/`, `api/`,
   `api/routes/`. Keep `__init__.py` files thin (package markers + a small
   re-export surface once modules exist).
2. `opm_ai/settings.py` using `pydantic-settings` to load `.env`. Exact keys
   (from `.env.example`):

   ```
   GROQ_API_KEY=your_groq_api_key_here
   NVIDIA_NIM_API=your_nvidia_nim_api_key_here
   OPENAI_API_KEY=your_openai_api_key_here
   OPENAI_BASE_URL=https://api.openai.com/v1
   TAVILY_API=your_tavily_api_key_here     # optional, web search; RAG/Phase 3 only
   OPM_FLOW_BINARY=/usr/bin/flow
   RESINSIGHT_EXECUTABLE=/usr/bin/ResInsight
   LOG_LEVEL=INFO
   ```

   All keys optional with sane defaults so `Settings()` never raises offline.
   `OPM_FLOW_BINARY` defaults to `/usr/bin/flow`, `RESINSIGHT_EXECUTABLE` to
   `/usr/bin/ResInsight`, `LOG_LEVEL` to `INFO`.
3. `loguru` logging configured once (level from `LOG_LEVEL`), imported by modules.
4. Editable install: `pip install -e .` so `import opm_ai` works and the `skipif`
   unit tests run.
5. Per-folder `context.md` in each new module dir (CLAUDE.md folder rule).

---

## 7. Risks and open questions

| Risk / question | Impact | Mitigation / who decides |
|-----------------|--------|--------------------------|
| `resfo` summary-to-DataFrame mapping is nontrivial | Postprocess (Phase 2) contract | Prototype `read_summary` against the shipped SPE1 `.ESMRY` early; verify `resfo>=5.0` API |
| Builder must emit a deck that passes the linter AND (later) actually runs | Builder contract | Phase 1 targets lint-pass only; `test_builder.py` defers Flow-run of generated decks. Real run needs tuned PVT/init (Part 4) |
| `rips`/ResInsight version mismatch | Postprocess bridge optional path | Pin `rips`; keep the bridge optional and degrade to Plotly-only |
| LLM model ids drift (Groq deprecations) | Chat/build quality | Config-driven model ids in settings; offline fallback returns `None` |
| System `opm.io` not on venv path | Only if a Part imports `opm.io` | Phase 1 uses subprocess + text parser; revisit if bindings needed |
| SPE1 has no REGIONS section | Linter rule design | REGIONS is optional; the linter must not require it (verified: SPE1 has RUNSPEC/GRID/PROPS/SOLUTION/SUMMARY/SCHEDULE only) |
| Secret leakage via `.env` | Security | `.gitignore` already ignores `.env`; never echo keys in logs |

Open questions (from `IMPLEMENTATION_PLAN.md`): long-running `/api/run` as
background task + polling (assumed) vs blocking; whether `opm.io` is adopted for
the linter later or the text parser stays.

---

## 8. Verification and done-criteria

Stage 0 is gated by `tests/unit/test_input_parser.py`.

- Prove: from `tests/`, `pytest tests/unit/test_input_parser.py -v` passes
  (fixtures found, `import opm_ai` succeeds, so the `skipif`ed classes run).
- Prove install: `pip install -e .` exits 0 and `python -c "import opm_ai"` works.
- Downstream gate map (each sibling doc owns its target):
  - 01 Runner: `integration/test_runner_spe1.py` (needs Flow; also needs Postprocess).
  - 02 Linter: `unit/test_linter.py`.
  - 03 Builder/LLM/CLI: `unit/test_llm.py`, `unit/test_cli.py`, `integration/test_builder.py`.
  - 05 Postprocess: `unit/test_plots.py` + the SPE1 summary/KPI reads.

Do not mark a stage done on a partial pass; paste the pytest output per
`IMPLEMENTATION_PLAN.md` conventions.

---

## 9. Future extensions

- Phase 3 Explainer/RAG (07-explainer.md): chromadb/llama-index over the Eclipse
  keyword HTML in `tests/eclipse*/` and deck comments; add those deps only then.
- Multi-user deployment, auth, and horizontal scaling (Part 8 tail).
- Broader physics templates in the Builder (WAG, CO2 store, gas cap) beyond the
  Phase 1 depletion/waterflood set.
- Adopt `opm.io` for a schema-accurate linter if the text parser proves limiting.

---

## Appendix A. Glossary

Deck sections (Eclipse/OPM `.DATA` order):

| Section | Purpose |
|---------|---------|
| RUNSPEC | Run dimensions, phases, units (`DIMENS`, `OIL`/`GAS`/`WATER`, `FIELD`/`METRIC`) |
| GRID | Cell geometry and rock (`DX`/`DY`/`DZ`/`TOPS`, `PORO`, `PERMX`) |
| PROPS | Fluid and rock-fluid properties (PVT tables, relperm: PVTO/PVDG/PVTW, SWOF/SGOF) |
| REGIONS | Region assignments (FIPNUM, SATNUM); optional, absent in SPE1 |
| SOLUTION | Initial state / equilibration (`EQUIL`) or `RESTART` for forecasts |
| SUMMARY | Which vectors to write (FOPR, WBHP, etc.) for time-series output |
| SCHEDULE | Wells and controls over time (WELSPECS, COMPDAT, WCONPROD, WCONINJE, TSTEP) |

Terms and decks:

- black-oil: three-component (oil/gas/water) model with gas dissolved in oil
  (`DISGAS`, factor Rs); the default physics for SPE1 and the Phase 1 templates.
- SPE1: canonical 10x10x3 (300-cell) FIELD-units black-oil deck, wells `PROD` and
  `INJ`; the primary TDD fixture (`tests/fixtures/spe1/SPE1CASE1.DATA`).
- SPE9: larger heterogeneous waterflood reference (Builder template source).
- Norne: realistic North Sea field deck (`NORNE_ATW2013.DATA`), MPI/complex-deck test.

KPI vectors (educationally important, per GUIDE 3):

| Vector | Meaning |
|--------|---------|
| WOPR | Well Oil Production Rate |
| WWCT | Well Water Cut |
| WBHP | Well Bottom-Hole Pressure |
| FOPT | Field Oil Production Total (cumulative) |
| FPR | Field (reservoir) Pressure |

(`WOPT:PROD`, the cumulative-oil vector for well `PROD`, is the specific column the
Runner integration test asserts.)

## Appendix B. Sibling document index

| Doc | Part | Module(s) | One-line summary |
|-----|------|-----------|------------------|
| 00-overview-and-architecture.md | 0 | `opm_ai`, `settings` | This doc: AIM, architecture, stack decisions, Stage 0 foundation |
| 01-runner.md | 1 | `opm_ai.runner` | Wrap `/usr/bin/flow` as a subprocess; structured `SimulationResult`, never raises |
| 02-linter.md | 2 | `opm_ai.linter` | Offline `Deck` parser + rule engine; `lint_deck` returns `LintResult` |
| 03-builder.md | 3 | `opm_ai.builder`, `opm_ai.llm`, `opm_ai.cli` | NL to deck via ModelSpec + Jinja2; auto-lint; LLM client with offline fallback; click CLI |
| 04-preprocess.md | 4 | `opm_ai.preprocess` | PVT/relperm correlations (Standing, Vasquez-Beggs, Corey/LET) to PROPS blocks |
| 05-postprocess.md | 5 | `opm_ai.postprocess` | `resfo` summary to KPIs to Plotly; optional `rips` ResInsight 3D snapshots |
| 06-chat-and-api.md | 6 | `opm_ai.api`, `frontend/` | FastAPI backend exposing modules as `/api/*`; React+Vite SPA consuming them |
| 07-explainer.md | 7 | `opm_ai.explainer` | Deferred RAG explainer (chromadb/llama-index) over keyword refs; Phase 3 |
| 08-deployment.md | 8 | `docker/`, `README.md`, CI | `docker compose up`; Dockerfile with Flow/ResInsight; GitHub Actions running SPE1 |
