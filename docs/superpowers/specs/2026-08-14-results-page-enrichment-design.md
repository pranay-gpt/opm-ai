# Results Page enrichment, Import Results, Export Graph

Date: 2026-08-14
Status: design — approved, implementation in progress
Branch: `feat/results-page-enrichment` (off `feat/v2-linter-grammar` @ `971ff00`;
the linter branch has added `6268320` since, see "Merge order" below)
Scope: Results Viewer (KPIs / Plots / 3D tabs), chat tools, Import Results, Export Graph

## Goal

Make the Results Viewer useful to a reservoir engineer. Today it shows 8 hardcoded
KPIs, 2 backend-generated plots, and the 3D grid; the engineer needs to see the
field's 4 highest-priority vector families from `eclipse_output_formats.json`,
choose which wells to compare, and be able to bring in results from a run that
happened somewhere else (their laptop, a CI artifact, a colleague's server).

Concretely, the user gets:

1. A **left-side control rail** on the KPIs and Plots tabs so they can pick
   which wells and which vectors are visible.
2. **Top-4 priority vector groups** (Field rates/cumulative/derived, Well
   rates, Well cumulative, Well injection) with auto-detected vector
   membership and one Plotly chart per group.
3. **3D cross-sections** (I/J/K plane slicing) and **well property overlay**
   (line colored by the active property along each well trajectory) added
   to the existing 3D viewer.
4. **Import Results**: a button that uploads summary/grid/restart/RFT files
   and registers them as a virtual job; the rest of the Results Viewer is
   unchanged because it already works against any job whose `output_dir`
   contains valid Eclipse files.
5. **Export Graph**: per-chart PNG / SVG (client-side via Plotly) and CSV
   download (new lightweight endpoint) for every chart on the Results page.
   CSV export supports **three frequencies**: `native` (the file's own
   report steps, no resampling), `monthly`, and `yearly`. Backend resampling
   because rate and cumulative vectors need different aggregation rules
   and we want the chat tools to reuse the same logic.
6. **Three new chat tools** so the engineer can ask "show WBHP for PROD1
   vs INJ1" in plain language and get a chat-bubble figure back.

**Operating principle — plot only what is present.** Nothing in this
design fabricates vectors. `categorizer.py` returns only the groups
that have at least one vector present in the DataFrame; `plot_groups.py`
emits a trace only for columns that exist; the KPI grid shows only KPIs
`extract_kpis` actually computed. The Plotly figures look sparse when
the run only had a handful of vectors — that is the correct behavior,
not a bug to paper over with placeholders or zero-filled series.

Explicitly out of scope (deferred, not promised):

- Region/block summary KPIs (the 3D viewer already covers region visualization).
- RFT/PLT parsing (different file family, low priority per the catalogue).
- LGR highlighting, fault-plane toggle (3D enhancements we deferred to keep
  this branch reviewable).
- Side-by-side comparison of two separate jobs.
- Persistence of imported results across server restarts (the job store is
  in-memory by design; re-import is cheap).

## Architecture

### Backend (`opm_ai/`)

**`opm_ai/postprocess/categorizer.py`** (new, ~100 lines, pure functions)

Takes a summary `pd.DataFrame` and returns `CategorizedVectors`, a TypedDict:

```python
class CategorizedVectors(TypedDict):
    field_rates: list[str]        # FOPR, FWPR, FGPR (when present)
    field_cumulative: list[str]   # FOPT, FWPT, FGPT
    field_derived: list[str]      # FWCT, FGOR, FPR (computed)
    well_rates: dict[str, list[str]]   # well_name -> [WOPR, WWPR, WGPR, WBHP, WGOR, WWCT]
    well_cumulative: dict[str, list[str]]  # well_name -> [WOPT, WWPT, WGPT]
    well_injection: dict[str, list[str]]   # well_name -> [WGIR, WWIR, WGIT, WWIT]
```

Detection rules:

- Field vectors: column starts with `F` and matches the field-keyword list.
- Well vectors: column contains `:` and the part before `:` matches a
  well-keyword list.
- Producer vs injector split: a well is a producer if any of
  `WOPR:{name}`, `WWPR:{name}`, `WGPR:{name}` has a positive max value
  (catches pure water/gas producers that report 0 oil); an injector if
  any of `WGIR:{name}`, `WWIR:{name}`, `WGIT:{name}`, `WWIT:{name}`
  has a positive value and the producer test fails. Wells with both
  positive production and positive injection appear in both groups.
- The well-keyword list is fixed and enumerated explicitly: well rates
  = `[WOPR, WWPR, WGPR, WBHP, WGOR, WWCT]`; well cumulative =
  `[WOPT, WWPT, WGPT]`; well injection = `[WGIR, WWIR, WOIR, WGIT,
  WWIT]`. Field-derived = `[FWCT, FGOR, FPR]`. Anything outside these
  lists is not categorized (left in the DataFrame for `kpi.py` to
  handle, not dropped).
- Empty groups are omitted from the response.

Same NaN / negative-zero sanitization as `kpi.py`. No I/O. 100% unit-tested.

**`opm_ai/postprocess/plot_groups.py`** (new, ~250 lines, pure functions)

One builder per group: `plot_field_rates(df, vectors)`, `plot_field_cumulative`,
`plot_field_derived`, `plot_well_rates(df, wells, vectors)`, etc. Each returns
a `go.Figure`. Selection args (`wells`, `vectors`) default to "all present" so
the unfiltered view still works.

Reuses `_sanitize_water_rate` and the `hovertemplate` style from the existing
`opm_ai/postprocess/plots.py`. Y-axis type (`linear` vs `log`) is taken from
a kwarg so the frontend can toggle without a re-fetch by calling
`Plotly.relayout(div, {'yaxis.type': 'log'})` on the cached figure (the
layout patch is in place; no second backend round-trip).

**`opm_ai/api/routes/results.py`** (extended)

Three new endpoints:

- `GET /api/results/{id}/categories` -> `CategorizedVectorsResponse` (same
  shape, JSON-safe).
- `GET /api/results/{id}/plot_group/{group}?wells=A,B&vectors=FOPR,FWPR&log=true`
  -> `PlotGroupResponse { figure_json: str }`. Figure is `""` on failure
  (F1.5 audit pattern: empty card on the client, trace in server log).
- `GET /api/results/{id}/csv?group=field_rates&vectors=FOPR,FWPR&freq=native`
  -> `text/csv` response. The CSV is the underlying summary DataFrame sliced
  to `TIME` + the requested vectors; the client does the per-well slicing
  for `well_rates` because the columns are already named `WOPR:PROD1`.

  `freq` is one of `native` (default), `monthly`, `yearly`. Resampling
  happens in `opm_ai/postprocess/resample.py` (new, ~60 lines) with rules
  pinned by vector suffix (see "Resampling rules" below). The endpoint
  returns a header row even when no rows match (same `TIME,\n` behavior
  as today).

Validation: `wells` and `vectors` query params must be non-empty strings
of safe identifiers (regex `[A-Za-z0-9_:,.-]+`). No path traversal —
the only filesystem access is the existing `job_output_dir(job)` which
already goes through `paths.validate_deck_path`.

**Resampling rules** (`opm_ai/postprocess/resample.py`, new):

The summary file's TIME column is whatever the deck asked Flow to write —
daily, monthly, yearly, or irregular. `freq=native` returns the file
verbatim. `freq=monthly` / `freq=yearly` resample with rules keyed off the
**last character of the column name** (the vector suffix):

| Suffix | Meaning | Aggregation per bucket |
|---|---|---|
| `R` | rate | `mean` — time-average rate over the bucket |
| `IR` | injection rate | `mean` |
| `T` | cumulative total | `last` — snapshot at bucket end |
| `IT` | cumulative injection | `last` |
| `IP` | in-place volume | `last` |
| `P`, `PR` | pressure | `mean` |
| `SAT` | saturation | `mean` |
| `OR` | gas-oil ratio | `mean` |
| `CT` | water cut | `mean` |
| `GP` | gas production rate | `mean` |
| anything else | unknown | `mean` (defensible default) |

Well-level columns inherit the rule from their suffix (`WOPR:PROD1` -> rate,
mean). TIME itself becomes the bucket-end timestamp via
`df.resample(rule).last().index`. Bucket boundary handling: if a vector
appears at multiple timesteps within a bucket, the rule is applied to
all values; if it appears zero times in a bucket, the row is dropped
(no zero-fill).

Implementation: a single `resample_summary(df, freq: str) -> pd.DataFrame`
function. `freq` is one of `"native"` (early return, copy of df), `"M"`
(monthly), `"Y"` (yearly). Uses `pd.DataFrame.resample` on a DatetimeIndex
derived from the `TIME` column. If the TIME column is not parseable as
datetime (rare but possible — some decks store report step index instead
of date), `resample_summary` falls back to step-based bucketing: floor of
`(step / days_per_bucket)` where `days_per_bucket = 30` for monthly, `365`
for yearly. Both code paths unit-tested.

**`opm_ai/api/routes/imported_results.py`** (new, ~180 lines)

`POST /api/imported-results` (multipart). Validates:

- At least one `*.SMSPEC` and one `*.UNSMRY` (or one `*.ESMRY`) — otherwise
  the Results Viewer can't show anything.
- Accepts but doesn't require `*.EGRID`, `*.GRID`, `*.UNRST`, `*.INIT`,
  `*.RFT`, `*.PRT`. Each is dropped into the per-job output dir.

Security model copied from `upload.py`: `tempfile.mkdtemp(prefix=...)`,
`_SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")`, defence-in-depth
`include_dir.resolve() not in target.parents` check, `max_part_size=256 MB`,
`max_files=5000`. No `.DATA` requirement (these aren't decks).

Returns `ImportedResultResponse { job_id: str, files_received: list[str],
warnings: list[str] }`. The `job_store` is extended with a `register_virtual_job`
helper that creates an in-memory `Job` with `status="completed"`,
`result={"output_dir": str}` — same shape as a finished real run, so every
downstream endpoint works without changes.

Virtual jobs are tagged `kind="imported"` in the store (additive enum).
The existing `/api/run/{id}` route still returns the right thing for them
because they never go through the runner.

**`opm_ai/api/routes/chat.py`** (extended, ~100 lines added)

Three new tools (each follows the existing async-tool pattern):

- `list_available_vectors(args)` -> `{"field_rates": [...], "well_rates":
  {"PROD1": [...], ...}, ...}`. No job_id needed — uses the "active job"
  the chat session knows about (same mechanism as `get_kpis`).
- `plot_well_vectors(args)` -> `{"figure_json": str, "wells": [...],
  "vectors": [...]}`.
- `compare_wells(args)` -> `{"figure_json": str, "wells": [...],
  "vector": "WBHP"}`. Single vector across multiple wells — most common
  comparison shape.

Each tool has a `compact_tool_result` rule that strips the Plotly JSON to
`{traces: [{name, first_3_points}]}` for LLM history (full figure goes to
the user over the WebSocket, never re-sent to the provider).

### Frontend (`frontend/src/`)

**Refactored `ResultsViewer.tsx`** — tab structure unchanged, layout changes:

- Tab strip (KPIs / Plots / 3D) stays at the top.
- KPIs and Plots tabs become a two-column flex: `<ControlRail>` on the left
  (~280 px, scrollable), `<ResultsPane>` on the right (scrollable content).
- 3D tab keeps the existing Grid3DViewer + its ControlPanel.
- Header gains: Import Results button, Export Graph menu (visible when at
  least one chart is rendered on the active tab).

**`frontend/src/components/results/ResultsControlRail.tsx`** (new, ~280 lines)

Pattern follows `viewer3d/ControlPanel.tsx`: collapsible sections, primitive
components (`Section`, `Field`, `Check`, `Sel`, `Num`). Props:

```ts
interface ResultsControlRailProps {
  categorized: CategorizedVectors;
  selectedWells: Set<string>;
  onWells: (s: Set<string>) => void;
  selectedVectors: Record<VectorGroup, Set<string>>;
  onVectors: (g: VectorGroup, s: Set<string>) => void;
  logScale: boolean;
  onLogScale: (v: boolean) => void;
}
```

Sections:

1. **Wells** — checkbox per well with role badge (PROD / INJ), "all producers",
   "all injectors", "all", "none" buttons.
2. **Vector groups** — one collapsible section per group with a checkbox per
   vector; "all" / "none" per group; groups with 0 vectors are hidden.
3. **Display** — log-scale toggle, line-style select (solid/dashed/dotted),
   per-well color toggle.

**CategorizedVectors state**: stored in `useAppStore` alongside
`lastResults`, keyed by `job_id`. Cleared on job change. Implementation
will add `setCategories(jobId, cats)` / `getCategories(jobId)` helpers —
parallel to the existing `setLastResults` pair, not a new store.

**`frontend/src/components/results/PlotCard.tsx`** (extracted from the
inline `PlotCard` in `ResultsViewer.tsx` today, ~120 lines — same
component is reused by ChatPanel's tool-result rendering, so a single
extraction serves both)

Renders one Plotly figure. Adds an export menu in the card header:

- **PNG** — `Plotly.downloadImage(div, {format: 'png', width, height, filename})`.
- **SVG** — same with `format: 'svg'`.
- **CSV (native)** — fetches
  `/api/results/{id}/csv?group=...&vectors=...&freq=native` (default).
- **CSV (monthly)** — same with `freq=monthly`.
- **CSV (yearly)** — same with `freq=yearly`.

All three CSV variants trigger a client-side download via a blob URL;
the filename suffix encodes the frequency so the user can tell them
apart (`PROD1_WBHP_native.csv` vs `PROD1_WBHP_monthly.csv`).

The export menu is a small `<details>` dropdown to avoid pulling in a popover
library. Empty figure JSON renders the same empty-state as today.

**`frontend/src/components/results/ImportResultsButton.tsx`** (new, ~180 lines)

Opens a modal containing:

- A `<input type="file" multiple>` accepting the Eclipse extensions.
- A list of selected files with a remove button.
- A static hint panel: "SMSPEC + UNSMRY (or one ESMRY) are required;
  EGRID/GRID/UNRST/INIT/RFT/PRT are optional." Hardcoded client-side
  so we don't burn a round-trip before the user has picked files.
- Submit button: `api.importResults(formData)` -> on success, calls the
  same `loadResults(jobId)` already used by the rest of the app.

**`frontend/src/types.ts`** and **`frontend/src/api/client.ts`** (extended)

New types: `CategorizedVectors`, `PlotGroupResponse`, `ImportedResultResponse`,
`CsvResponse` (just a string). New `api` methods: `categories(id)`,
`plotGroup(id, group, opts)`, `csv(id, group, vectors)`, `importResults(form)`.

**`frontend/src/components/viewer3d/ControlPanel.tsx`** (extended, ~80 lines added)

Two new collapsible sections:

- **Cross-section**: axis select (`I` / `J` / `K`), index slider with min/max
  bound to the active axis. Renders a second `<canvas>` overlay on top of
  the existing 3D scene showing the clipped slice with the active colormap
  (the slice data comes from the same `gridProperty` endpoint already used
  for the volume render — no new endpoints needed).
- **Well overlay**: well selector, "show wells in 3D" already exists; this
  adds "show property-along-trajectory" which draws a 2D plot below the
  3D canvas with depth (Y) vs property value (X), one line per active well.
  The trajectory data comes from `gridWells` (already exists).

**`frontend/src/components/ChatPanel.tsx`** (extended, ~80 lines added)

Tool result rendering gains a case for `plot_well_vectors` and `compare_wells`:
renders the embedded `figure_json` as a `<PlotCard>` inside the chat bubble
(same `PlotCard` component — single source of truth for figure rendering).

## Data flow

```
User clicks Import Results
  ImportResultsButton modal
    -> FormData(files)
  POST /api/imported-results
    -> backend: validate extensions, mkdir temp dir,
       copy files into it, register virtual job
  <- { job_id, files_received, warnings }
  frontend: setCurrentJob({ job_id, status: "completed" })
  existing /api/results/{job_id} loaders fire

Results Viewer mounts -> KPIs tab
  GET /api/results/{id}/categories   (cached in store)
  GET /api/results/{id}              (existing, KPI values)
  ControlRail renders wells + vector groups
  KPI grid stays as a flat card list (top 4 priority KPIs always visible)

User opens Plots tab
  ControlRail selection state drives the right pane:
    for each non-empty group, render a PlotCard
    each PlotCard lazy-fetches /plot_group/{group}?wells=...&vectors=...
      on first render; memoized by (group, wells, vectors)
    log-scale toggle patches the cached layout.yaxis.type client-side

User opens 3D tab
  Grid3DViewer mounts (unchanged core)
  + Cross-section panel (axis + K index)
  + Well overlay panel (property-along-trajectory line)

User opens Chat, asks "show WBHP for PROD1 vs INJ1"
  LLM calls plot_well_vectors({wells: ["PROD1", "INJ1"], vectors: ["WBHP"]})
  backend returns Plotly JSON
  ChatPanel renders the figure inside the chat bubble

User clicks Export Graph > PNG / SVG / CSV on any PlotCard
  PNG / SVG: Plotly.downloadImage (no backend)
  CSV: GET /api/results/{id}/csv?group=...&vectors=... -> blob download
```

## Components and boundaries

| Unit | Purpose | Deps | Lines | Test |
|---|---|---|---|---|
| `categorizer.py` | DataFrame -> CategorizedVectors | postprocess/summary | ~100 | unit + fixtures |
| `plot_groups.py` | DataFrame + selection -> Plotly figure | postprocess/summary | ~250 | unit + fixtures |
| `resample.py` | DataFrame + freq -> resampled DataFrame | postprocess/summary | ~60 | unit + fixtures |
| `routes/results.py` (added routes) | categories / plot_group / csv | categorizer, plot_groups, resample, kpi | +140 | integration |
| `routes/imported_results.py` | Multipart upload + virtual job | job_store, paths | ~180 | integration |
| `routes/chat.py` (added tools) | list / plot / compare well vectors | categorizer, plot_groups | +100 | integration |
| `ResultsControlRail.tsx` | Tab-specific well + vector selector | types | ~280 | RTL |
| `PlotCard.tsx` | Plotly renderer + export menu | plotly.js | ~120 | RTL |
| `ImportResultsButton.tsx` | Modal file picker + submit | api | ~180 | RTL |
| `ChatPanel.tsx` (added rendering) | Render figures inside chat bubbles | PlotCard | +80 | RTL |
| `viewer3d/ControlPanel.tsx` (added sections) | Cross-section + well overlay | engine.ts, gridWells | +80 | RTL |

Each unit has one job, communicates through typed props/JSON, can be tested
in isolation.

## Error handling

- **Bad file types in import**: `validate_imported_files` raises 400 with
  the offending filename; UI shows the error inline. Mirrors `upload.py:140`.
- **Missing SMSPEC+UNSMRY pair**: import succeeds but `/api/results/{id}`
  returns 400 "No summary data found"; UI shows the existing empty-state
  with a "fix files and re-import" hint (no new state).
- **Plot generation failure for a group**: empty string returned, PlotCard
  renders the existing empty card (F1.5 audit pattern, no new states).
- **CSV request with no matching vectors**: backend returns 200 with header
  row only (`TIME,\n`); PlotCard shows "No data in this selection" hint.
- **Cross-section K out of range**: clamped to grid bounds; UI shows the
  clamped value next to the slider.
- **LLM tool result too large**: `compact_tool_result` strips the Plotly
  JSON to `{traces: [{name, first_3_points}]}` per the existing
  `get_kpis` precedent. Full figure goes to the user over WebSocket.
- **Import file > 256 MB**: Starlette multipart parser rejects the part
  with 413 before the route handler runs. Mirrors upload.py limits.

## Testing

### Unit

- `tests/unit/test_categorizer.py` (10 cases):
  empty df, only field, only well, mixed, no positive producer, mixed
  producer/injector, all groups empty, RFT column present (ignored),
  weird column names, duplicate well names with different roles.
- `tests/unit/test_resample.py` (8 cases):
  native is identity, monthly rate = mean, monthly cumulative = last,
  yearly pressure = mean, datetime vs step-index fallback, mixed
  suffixes in one frame, empty bucket dropped, missing vector in bucket.
- `tests/unit/test_plot_groups.py` (15 cases):
  one per group, multi-well, log-scale, negative-zero sanitization,
  empty wells, missing vectors, all-scalar columns, single timestep.
- `tests/unit/test_import_validation.py` (5 cases):
  no SMSPEC, only SMSPEC, ESMRY instead of pair, path traversal in
  filename, missing include/.

### Integration

- Extend `tests/integration/test_results_plot_failure.py`:
  one failing group + others succeed; CSV export; categories endpoint.
- `tests/integration/test_imported_results_route.py` (8 cases):
  happy path, missing SMSPEC, .EGRID-only, mixed extensions, virtual
  job appears in `/api/results/{id}` after import, grid/info works on
  virtual job, path-traversal attempt, oversized file rejected.
- `tests/integration/test_chat_tools_results.py` (6 cases):
  list_available_vectors, plot_well_vectors, compare_wells, compact
  result shape, tool name not registered, tool args validation.

### Frontend

- `frontend/src/components/results/ResultsControlRail.test.tsx`:
  rendering, well selection, vector selection, log toggle.
- `frontend/src/components/results/PlotCard.test.tsx`:
  empty figure, happy render, export menu opens.
- `frontend/src/components/results/ImportResultsButton.test.tsx`:
  file picker, validation, submit, error display.
- Extend `frontend/src/components/ResultsViewer.test.ts`:
  new tab structure, virtual job load, chat tool integration.

Target: 332 (current) + ~60 new tests = ~392 total, all green before merge.

## Branch and commit strategy

Branching off `feat/v2-linter-grammar` @ `971ff00` (current HEAD; the
uncommitted changes on `opm_ai/linter/v2/catalogue/keywords.py` belong
to the linter branch worker and are not touched here).

New branch: `feat/results-page-enrichment`.

10 commits, each green:

1. `opm-ai: results — categorizer (field/well/injection groups) + tests`
2. `opm-ai: results — plot_groups (one builder per vector family) + tests`
3. `opm-ai: results — resample (native/monthly/yearly) + tests`
4. `opm-ai: api — /categories, /plot_group, /csv endpoints + tests`
5. `opm-ai: api — /imported-results (virtual-job registration) + tests`
6. `opm-ai: api — chat tools (list_vectors, plot_well_vectors, compare_wells) + tests`
7. `frontend: results — left-side control rail + extracted PlotCard`
8. `frontend: results — Import Results button + modal`
9. `frontend: viewer3d — cross-section + well property overlay`
10. `frontend: results — Export Graph (PNG/SVG/CSV at 3 frequencies) + ChatPanel figure rendering`

### Merge order (post-completion)

The linter branch (`feat/v2-linter-grammar`) is in active development.
At spec-write time the branch tip is `971ff00` (this branch's parent).
At implementation-start time the linter branch has added `6268320`
(GRIDUNIT/ASSIGN widening). The two branches touch disjoint files
(linter = `opm_ai/linter/`; this = `opm_ai/postprocess/` +
`opm_ai/api/routes/results.py` + `frontend/src/...`), so the merge
should be conflict-free regardless of order.

Plan: when both branches are ready for `main`, the linter branch
rebases onto this branch's tip (or vice versa — both work), then
both merge into `main`. If linter finishes first, it merges into
`main` and we rebase this branch onto updated `main` before merging.
If this branch finishes first, we hold and merge when linter is ready.

## Decisions recorded

- **Streaming vs lazy plot generation**: streaming. Categorizer output is
  tiny; plot generation is fast (a few hundred ms per group, all groups
  combined < 2 s on the test decks). Lazy would add cancellation,
  in-flight tracking, and per-vector endpoints for marginal gain.
- **CSV via backend, not client-side**: client has the summary DataFrame
  cached but slicing per-well is the same complexity either way and a
  small server endpoint keeps the JSON contract consistent for both the
  chat tools and the UI.
- **Plotly `downloadImage` for PNG/SVG**: built-in, no extra deps, handles
  hi-DPI canvases correctly.
- **No new dependency for the popover**: `<details>` element handles the
  Export menu and Import modal's file picker. Keeps the bundle where it is.
- **Virtual jobs die with the server**: deliberate; the job store is
  in-memory by design. Re-import is a few clicks.
- **Region/block summary KPIs skipped**: the 3D viewer covers the same
  data with more context; KPIs would duplicate.
- **No side-by-side job comparison**: out of scope; would need a new
  layout primitive and selection state that crosses tab boundaries.
- **CSV resampling on the backend, not the client**: the summary
  DataFrame is already in memory after the first `/categories` call,
  but resampling needs different aggregation rules per vector suffix
  (mean for rates, last for cumulative, etc.) and the chat tools need
  the same logic. Doing it once on the server keeps the chat and the
  UI consistent and the response small.
- **Resampling rules keyed by vector suffix**: enumerated in the
  "Resampling rules" subsection above. The default for unrecognized
  suffixes is `mean` — a wrong default that errs toward smoothness
  rather than toward invented precision, and documented so future
  maintainers see the assumption.
