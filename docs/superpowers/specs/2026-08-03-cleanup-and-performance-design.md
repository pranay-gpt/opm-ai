# Cleanup and performance pass

Date: 2026-08-03
Status: awaiting review

## Goal

Remove dead weight, cut the duplication that costs real maintenance, and fix
the two performance problems a user can feel. Keep the app a single-user lab
tool. Every stage lands as its own commit with the suite green.

Explicitly out of scope, by decision: authentication, a shared job store,
multi-worker support, key persistence with an audit trail. Those are a
different class of work and the app is not multi-user today.

## What the audit actually found

Six read-only subagents audited backend duplication, frontend duplication,
API contracts, performance, dead code, and enterprise readiness. Their
load-bearing claims were re-verified by hand before landing here, because
several were wrong:

| Claim | Verdict |
|---|---|
| Job store has no lock, unbounded growth | False. `job_store.py:17` holds a `Lock`; `:26` evicts past a cap. |
| CORS is `allow_origins=["*"]` | False. `server.py:59` pins `http://localhost:5173`. |
| `statistics()` is dead code | False. Called at `grid.py:338` and `:378`. |
| Spinner SVG duplicated in 10 files | Overstated. 10 occurrences across 5 files. |
| ~626 duplicated frontend lines | Overstated. Roughly 90 lines are honestly recoverable. |
| `meshFormat.test.ts` has never run | False. It runs today and all 19 checks pass. |

The corrected findings are what this plan implements. Nothing below is
included on a subagent's word alone.

## Stage 1: delete dead dependencies and dead code

Pure deletion. No behaviour change.

- `rips` (`pyproject.toml:16`). Zero imports in `opm_ai/` or `tests/`. It is
  the ResInsight gRPC client, and the packaged ResInsight ships without gRPC,
  so it could never have connected. Every install pays for it.
- `react-plotly.js` and `@types/react-plotly.js` (`frontend/package.json`).
  Never imported; the code uses `plotly.js-dist-min` directly.
- `plotly.js-dist` (`frontend/package.json`). Both the full and `-min` builds
  are declared, only `-min` is imported. 4.7 MB of duplicate.
- `cell_volumes()` (`postprocess/grid3d.py:315`). Only its own unit test calls
  it. Delete the function and its test together.

Verification: `pytest` green, `npm run build` green, and `pip install -e .`
resolves without `rips`.

## Stage 2: consolidate the duplication that costs something

Only the cases where a change must currently be made in several places.

- `_has_keyword` is byte-identical in five linter rule files (`grid.py:10`,
  `props.py:10`, `runspec.py:10`, `schedule.py:10`,
  `solution_summary.py:9`). A regex fix today needs five edits and one miss is
  a silent false negative. Move to `linter/rules/helpers.py`.
- `_get_keyword_values` is near-identical in three of those files, differing
  only in whether values are cast to float. Same helper module, with an
  `as_float` flag.
- Frontend: a `<Spinner>` and an `<ErrorBanner>` under
  `frontend/src/components/ui/`. Ten spinner occurrences across five files,
  eight error-banner occurrences across five. This is roughly 90 lines and,
  more usefully, one place to change error styling.

Not doing: the `useAsyncAction` hook the audit proposed. It would touch eight
components to save a `try/finally`, and the components' loading semantics
differ enough that the hook would need options to model them. The abstraction
costs more than the repetition.

Verification: `pytest` green (linter rules are well covered by
`test_linter_negative.py`), `npm run build` green, and the app renders.

## Stage 3: performance

Two changes, both small, both user-visible.

- Code splitting. The production bundle is one 5.8 MB chunk. `three` is 26 MB
  on disk and Monaco is imported eagerly by three separate components, so
  opening the Home page downloads the deck editor and the plotting library.
  Add `manualChunks` for `three`, `plotly`, and `monaco` in `vite.config.ts`,
  and `React.lazy` the route-level components.
- `GZipMiddleware` in `create_app()`. JSON responses are uncompressed and a
  Plotly figure runs 200-500 KB. One line. Binary grid endpoints are already
  incompressible and the middleware's `minimum_size` leaves them alone.

Verification: record bundle chunk sizes before and after; confirm the 3D
viewer still loads and renders a grid in the browser on both ports.

Deliberately deferred: the UNRST re-scan the performance audit flagged as its
top finding. The claim is that stepping through 50 timesteps re-reads a 72 MB
file each time. The scale is real but SPE1 is small enough that it does not
show, and the fix is an offset index into the restart file, which is a real
change to `grid3d.py` with real regression risk to the viewer. It wants its
own spec, its own before/after measurement on Norne, and its own review. Not
bundled into a cleanup pass.

## Stage 4: contract fix and test wiring

- `WSServerMessage.tool_result.result` is typed `string` in `types.ts:235`,
  but the backend sends a dict (`chat.py:420`). Nothing crashes today because
  the consumer happens not to call string methods on it, which is luck, not
  design. Retype to `Record<string, unknown>` and fix the consumer.
- Wire `meshFormat.test.ts` into `npm test`.

On the test runner: the audit recommended adding Vitest, and that
recommendation was based on a false premise. The file is not an unwired Vitest
suite. It is a deliberate esbuild-based assert script whose header explains
why ("No test framework is installed... there is no tsx here"), and it passes
all 19 checks today. Node here is 18.19.1, which does run Vitest 2.x, but
adding Vitest means adding a dependency and rewriting a working file to suit
it.

So: add a `test` script to `frontend/package.json` that runs the existing
esbuild self-check, giving one command that works. If we later want component
tests, Vitest earns its place then, on its own merits.

Verification: `npm test` exits 0 and prints the 19 checks.

## Risks

The linter helper extraction (Stage 2) is the only change that touches
simulation-affecting logic. It is covered by `test_linter_negative.py` (458
lines), and the extraction is mechanical. Everything else is deletion,
configuration, or presentational.

Code splitting can break a lazily-loaded route if an import has a side effect
that was previously guaranteed to run eagerly. Checked in the browser on both
ports before the stage is called done.

## Verification at every stage

`pytest` (332 passed, 2 skipped today), `npm run build`, and for the stages
that touch the UI, a browser check that the 3D viewer renders a grid. Anything
that cannot be shown green does not get committed.
