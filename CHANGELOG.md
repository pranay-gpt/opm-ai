# Changelog

All notable changes to OPM-AI are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/).

> Version note: the `0.2.0` block below was written ahead of a release and
> was never tagged or cut. `v0.1.0` was the last actual tag, so this release
> is `v0.1.1` as shipped. The `0.2.0` notes remain accurate as a record of
> work that landed before it.

## [0.1.1] - 2026-10-03

Context-aware reservoir builder: a step-by-step interview that asks one
section at a time, plus direct ingestion of grid, table, and keyword
files.

### Added

- Deterministic interview engine (`opm_ai/builder/interview/`): a
  23-question catalogue across 7 sections, plus dynamic per-well
  questions. Pure functions over `(spec, answers)` with no server-side
  session: the client owns the answers dict and round-trips it on every
  call, so a reload resumes exactly where the user left off.
- File and paste ingestion (`ingest.py`): GRDECL/SPECGRID fragments,
  PORO/PERMX/PHIE arrays, numeric grids, and PVDG/PVT tables are
  detected by format, parsed, and folded into the spec as resolved
  values. Upload and paste produce byte-equal specs.
- Stateless HTTP surface: `POST /api/interview/next`,
  `POST /api/interview/finish`, `POST /api/ingest/parse`,
  `POST /api/ingest/upload`.
- `InterviewPanel` in the Deck Builder: progress bar, answer/skip per
  question, restart, and build-from-answers.
- Semantic validation rules (`rules.py`) surface non-fatal findings
  inline, e.g. a gas cap declared without a GOC depth, a well placed
  deeper than the grid, or a `dz` list whose length disagrees with `nz`.

### Fixed

- EQUIL datum depth was pinned to the SPE1 default (8400 ft) regardless
  of the grid. It is now clamped to the grid midpoint when that default
  falls outside the model span; default decks stay byte-identical.
- `ReservoirSpec.dx/dy` accepted lists but `base.j2` string-multiplied
  them and the METRIC conversion multiplied a list by a float. Both now
  expand per layer, and `dx_list`/`dy_list` are only defined when the
  spec actually carries a list so golden decks do not drift.
- `field_units=False` was silently ignored and every deck rendered FIELD.
  It is now honoured, with a `ValueError` for METRIC-without-fluid
  because the built-in PVT tables are FIELD-only.
- Tokenizer classified bare-exponent (`1E5`, `3E-6`) and Fortran
  D-exponent (`2.5D+01`) real literals as UNKNOWN, silently discarding
  them from real exports.
- `use_llm` was ignored on the REST build path; the flag now selects the
  LLM extractor and falls back to offline extraction when it is
  unavailable, tagging the result `extracted` accordingly.
- The fluid branch of `_compute_template_context` was stranded as dead
  code when the METRIC guard was added as an `elif` after a two-line
  header, which silently pinned every deck with a fluid descriptor to the
  hardcoded SPE1 PVT tables. Two guards now hold the branch open.
- Restart in the interview panel cleared state but did not refetch, so
  the panel rendered blank with progress stuck at the pre-restart count.

Found by code review after the first browser pass:

- Picking a scenario could deadlock the interview. Question applicability
  is a predicate over the spec, but `/interview/next` evaluated the catalog
  against the extraction-only spec, so answering "gas cap" never made the
  GOC question reachable while rule R04 blocked on a missing one, and
  `/interview/finish` returned 422 with no answer available. The engine now
  folds collected answers before evaluating the catalog, iterating to a
  fixed point because an answer can change applicability. All seven
  scenarios reach a lint-passing deck.
- The gas-cap GOC question was `blocking` with a default of `None`, so
  skipping it tripped R04 forever. Its default is now a quarter of the way
  down the grid.
- Wells were never asked their type, leaving the "waterflood with no
  injector" block with no answer the user could give. Per-well type
  questions now exist and gate the PROD/INJ controls; that block names a
  well-type question rather than the already-answered scenario.
- The RSVD clamp was dropped alongside the METRIC guard, leaving its
  comment behind with no statement. Every deck carrying a fluid descriptor
  rendered the hardcoded SPE1 RSVD of 1.27 while the table max was
  computed and discarded.
- `detect_format` sniffed for a bare numeric grid before the leading
  keyword. Real GRDECL exports write one value per line, so a `PERMX`
  fragment was detected as a grid and its permeability written into
  porosity as 100.0, which the linter only warns about, so the deck still
  linted clean.
- Result-file rejection was a substring test, so `INIT` matched the word
  "initial" and a paste headed with `-- initial porosity estimate` was
  refused as an unreadable EGRID.
- The no-DIMENS ingest path collected distinct values with `sorted(set(...))`,
  silently re-ordering a layer profile: a 500/100/200 three-layer
  permeability became 100/200/500, a physically different reservoir with no
  finding recorded.
- An ingested array longer than `nx*ny*nz` was truncated silently.
- `apply_ingest` dropped any patch key the model does not carry, so a SWOF
  table parsed fine and was then discarded while the UI reported a
  successful read.
- R02's datum fallback disagreed with the builder's own clamp, blocking
  decks the builder renders clean on thin reservoirs.
- R07 checked only the upper grid bound, so an index of 0 passed; grid
  indices are 1-based at both ends.
- `csv_number` answers hit `float()` unguarded, surfacing a stray token as
  a bare 500 instead of a message naming it.
- The persisted interview answers slice included the whole ingested file
  text, which exceeds the localStorage quota on a multi-megabyte upload;
  zustand does not guard `setItem`, so the error killed the render.
- `detect_format` uppercased the whole upload but inspected 200
  characters, doubling peak memory on a large file.

### Design invariants

- **Never breaks**: every question is skippable, and a skip records the
  declared default server-side, so the terminal state always builds a
  deck.
- **Stateless**: no server-side session; the client owns the answers.
- **Provenance triad only**: every value is tagged `extracted`,
  `defaulted`, or `user_override`.
- **Never mean-average**: per-cell variation is refused by name rather
  than collapsed into a single representative number.

## [0.2.0] - 2026-08-19

### Added

- Results Viewer enrichment (Task 11): dynamic grid layout with 1 to 4
  columns, per-property plot toggle (one vector per graph), log-scale axis
  support, Field/Metric unit conversion, and CSV export at native,
  monthly, and yearly frequencies
- Graph export from individual Plotly plots to PNG, SVG, and CSV
- Linter v2 facade: `LinterAPI` with `LinterCache` (LRU, deepcopy,
  thread-safe) and `LinterExecutor` (sync/async submit with timeout)
- `LinterError` taxonomy and source-extension guard so non-`.DATA` files
  are rejected early
- `/api/lint/apply-fix` endpoint with server-side drift-check, plus a
  one-click "Apply" UI in the validation panel
- AI chat tools: `list_vectors`, `plot_well_vectors`, `compare_wells`,
  with WebSocket tool-call routing through `LinterAPI`
- `Import Results` button and modal that registers externally produced
  runs as virtual jobs
- 3D viewer: cross-section planes and well property overlay
- Keyword catalogue expansion: NNC, EDITNNCR, PLMIXPAR, PLYMAX,
  DRSDT(R) multi-record support; +455 clean fixtures now pass the linter
- UNITS / ASSIGN / DEFINE keyword specs and UDQ symbol harvesting
- Plot groups refactor: one builder per vector family (field rates,
  field derived, well rates, well cumulative, well injection); clean
  resampling at native/monthly/yearly frequencies

### Changed

- Chat tool entry points routed through `LinterAPI` (tool_lint_deck and
  tool_build_deck) for consistent caching and error handling
- Deck Editor validation panel now uses the same cached `LintResult` as
  the linter API, eliminating duplicate work between Check and one-click
  fix
- Frontend split the control rail into a left-side `ControlRail` with
  extracted `PlotCard` primitives; ChatPanel tool results preserve the
  original `tool_name` for downstream figure rendering
- API additions: `/categories`, `/plot_group`, `/csv`,
  `/imported-results` endpoints

### Fixed

- L013 out-of-order warnings suppressed when section ordering is
  semantically valid (the rule was producing false positives on
  catalogue-validated decks)
- Deck editor line-jump regression: clicking a lint error now scrolls
  the Monaco editor to the correct source line on first click, even
  after the panel has been re-rendered
- Stuck `inFlightRef` guard in the lint UI that silently swallowed user
  clicks was dropped
- Results plots tab: data now flows from `plot_groups` (FWCT column
  handling, water-rate sanitisation) instead of the legacy plots
  importer, fixing missing-field graphs on black-oil runs
- ChatPanel tool results: `tool_name` field is preserved end-to-end so
  figures render in the conversation transcript

### Removed

- Legacy `api.lint_deck` shadowing of the package-level `lint_deck`:
  the package surface now exposes `lint_deck` (L1 only) plus
  `default_api.lint_deck_combined` for callers that need the merged
  view
- Unused `job_output_dir` import in `imported_results`
