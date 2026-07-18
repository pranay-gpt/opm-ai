# OPM-AI Build Status and Resume Point

Living document. Read this FIRST after any context clear, before touching code.
Last verified: 2026-07-11.

## TL;DR for a fresh session

1. Read this file, then `docs/conversations/README.md`, then `00-overview-and-architecture.md`.
2. The plan docs `01-08` are the DESIGN SPEC to build toward. They were written assuming
   `opm_ai/` was empty. It is not (see below), but the decision is to treat the existing
   code as a throwaway reference sketch and rewrite each module cleanly against the specs.
3. Hard API contract = `BUILD_GUIDE.md` section 4 + the test files. Do not change a
   signature without updating its asserting test.
4. Work stage by stage (see `IMPLEMENTATION_PLAN.md`). Each stage compiles and passes its
   named test before the next. Commit per stage.

## Verified environment (2026-07-11)

| Fact | Value | How verified |
|------|-------|--------------|
| OPM Flow | `flow 2026.04` at `/usr/bin/flow`, runs SPE1 in ~0.5s | `flow --version`; timed run |
| Python | 3.12.3 | `python3 --version` |
| venv | `/home/parallels/opm-ai/.venv`, `include-system-site-packages = false` | `pyvenv.cfg` |
| resfo | 5.0.1, importable in venv | `import resfo` |
| rips | importable in venv | `import rips` |
| opm / opm.io / opm.simulators | ONLY on system python (`/usr/bin/python3`), NOT in venv | import tests |
| pandas / numpy / plotly / pydantic / pydantic-settings / jinja2 / click / groq / openai / loguru / uvicorn | all in venv | import tests |
| fastapi | NOT installed | `import fastapi` fails |
| streamlit | 1.58 installed (legacy, to be removed) | `import streamlit` |
| pytest | 9.1.1 | `import pytest` |
| git | NOT initialised (`.git/` empty, `git rev-parse` fails) | `git` |

Consequence of the venv flag: any module that needs `opm.io`/`opm.simulators` will not
import under the venv until either the venv is recreated with
`--system-site-packages`, or those are added another way. The runner uses a subprocess to
`flow`, so Phase 1 does NOT need the bindings. Keep it that way unless a stage requires them.

## Current code state: throwaway reference sketch

`opm_ai/` currently holds ~2036 lines across 20 `.py` files + 1 `.j2`, produced during the
doc-generation workflow. ALL 33 tests pass (22 unit + 11 integration, including a real
end-to-end SPE1 Flow run). Per user decision (2026-07-11), this code is treated as a
REFERENCE SKETCH, not the foundation: each module is rewritten cleanly against its spec doc
as we reach its stage. Salvage ideas/values from it, but do not assume it is correct.

Modules present (all to be rewritten): `settings.py`, `cli.py`, `llm/client.py`,
`builder/{builder,extract,models}.py` + `templates/base.j2`, `linter/{deck,linter}.py`,
`runner/{runner,models}.py`, `postprocess/{summary,kpi,plots,resinsight_bridge}.py`.
Not present: `api/` (empty dir), `preprocess/`, `explainer/`, `frontend/`.

## Defects the current tests do NOT catch (fix in the rewrite)

These are real, verified failures hidden by weak assertions. The rewritten code plus
tightened tests must eliminate them.

1. **build_deck emits invalid decks.** `base.j2` line 1 is a stray Python docstring
   `"""Jinja2 template ..."""`. It renders into the `.DATA` file, and Flow rejects it:
   `String """..."" not formatted as valid keyword`. Generated decks do NOT run, yet
   `test_build_deck_depletion` passes because it only greps for section-name substrings and
   the builder test explicitly defers the Flow run. FIX: template must contain only deck
   text; add a test that actually runs a built deck through Flow (or at least `flow --check`).

2. **Linter has no real severity model.** `lint_deck` downgrades most keyword problems to
   warnings so both fixtures pass. It will also pass genuinely broken decks. The spec in
   `02-linter.md` section 4.3 defines the intended ERROR/WARNING/INFO model. FIX: implement
   that, and add negative-case tests (a deck that SHOULD fail).

3. **Config/env drift** (see next section) is not exercised by any test.

## Reconciled decisions and drift to fix during rewrite

Authoritative stack (from `BUILD_GUIDE.md` section 2), unchanged:
React+Vite+TS front / FastAPI+Uvicorn back; `resfo` for output; Groq + OpenAI-compatible
LLMs, offline returns None; RAG deferred to Phase 3.

Concrete cleanups the rewrite/Stage-0 owns:

| Item | Current | Target |
|------|---------|--------|
| `pyproject.toml` deps | lists `streamlit`; no `fastapi`, no `click` | drop `streamlit`; add `click`, `fastapi`, `uvicorn[standard]` (uvicorn already installed) |
| `pytest.ini` | `[tool:pytest]` header -> pytest IGNORES it; markers unregistered | rename to `[pytest]` or move to `pyproject [tool.pytest.ini_options]`; register `slow`/`integration`/`unit` |
| `console script` | `opm-ai` entry not installed | re-run `pip install -e .` after pyproject fix so `opm-ai` works |
| env var name | settings uses `OPM_FLOW_PATH`; `.env.example` says `OPM_FLOW_BINARY` | pick ONE (recommend `OPM_FLOW_BINARY`, matches `.env.example` and `00-overview`); align settings + docs |
| env keys | `.env.example` has `NVIDIA_NIM_API`, `TAVILY_API`, `RESINSIGHT_EXECUTABLE`; settings lacks them and adds `API_*`,`FRONTEND_URL`,`FIXTURES_PATH` | reconcile the two lists; document every key settings reads |
| runner flow path | `runner/models.py` hardcodes `/usr/bin/flow` | read from `settings` |
| SPE1 fixture path in tests | absolute `/home/parallels/opm-ai/...` | keep working, but new tests should use a fixture/config path |
| `test_runner_spe1.py` | top-imports `postprocess` (Phase 2 modules) | in Phase 1, gate with `importorskip` or provide minimal postprocess stubs |

Open cross-doc inconsistency to resolve when we reach Phase 2 (noted in README Consistency
notes): `08-deployment.md` uses a ResInsight container image while `05-postprocess.md`/
`00-overview` assume host `/usr/bin/ResInsight`. Exposed port chosen: 8000 (uvicorn);
legacy 8555 (Streamlit) dropped.

## Build order (see IMPLEMENTATION_PLAN.md for detail)

Phase 1 (v1): Stage 0 skeleton+settings+config-cleanup -> Runner -> Linter ->
Builder+LLM+CLI. Phase 2 (v1.1): Postprocess+ResInsight -> FastAPI backend -> React
frontend -> Preprocess PVT. Phase 3 (v1.2): Explainer/RAG.

## Done-gates per stage (proof required)

Run from `tests/` with the venv python. A stage is done only when its named test passes and
you paste the output.

- Stage 0: `pytest tests/unit/test_input_parser.py -v`
- Runner: `pytest tests/integration/test_runner_spe1.py -v` (needs Flow; gate postprocess import)
- Linter: `pytest tests/unit/test_linter.py -v` + new negative-case test
- Builder+LLM+CLI: `pytest tests/unit/test_llm.py tests/unit/test_cli.py tests/integration/test_builder.py -v` + new "built deck runs in Flow" test
- Postprocess: `pytest tests/unit/test_plots.py -v` + SPE1 end-to-end summary/KPI

## Session log

- 2026-07-11: Wrote plan docs `00-08` + README. Verified environment and existing code.
  Found the package is not empty and tests pass but miss real defects (above). User chose to
  treat existing code as throwaway reference. Reconciled drift into this file and rewrote
  `IMPLEMENTATION_PLAN.md`. Next action: begin Stage 0 rewrite (skeleton + settings +
  pyproject/pytest cleanup).
- 2026-07-18: User added `docs/Reference_UI.png` (4-panel visual design). Extracted complete
  design system to `UI_DESIGN_SPEC.md` (dark blue/cyan palette, Monaco editor, section tree,
  3D ResInsight grid, Plotly charts). Updated `06-chat-and-api.md` with visual reference
  section. Created tasks #5-9 for Stage 0.5 (config reconciliation + test tightening + git
  init). **STAGE 0.5 COMPLETE** - All 5 tasks done: pyproject.toml fixed (streamlit removed,
  click/fastapi/uvicorn added), pytest markers registered in pyproject.toml, env vars
  reconciled (OPM_FLOW_BINARY canonical), negative tests added (7 xfail documenting defects,
  8 xpass showing partial linter coverage), git initialized with first commit (dfa6d82).
  Tests: 33 passed, 7 xfailed, 8 xpassed. Console script `opm-ai` installed and verified.
  Next: Stage 1 (Runner rewrite).
