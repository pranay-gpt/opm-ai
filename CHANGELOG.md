# Changelog

All notable changes to OPM-AI are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/).

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
