# opm_ai/postprocess - Results Processing

Last updated: 2026-07-22. Status: complete (Stage 4 + Stage E field KPIs + Stage 15 bridge).

## Purpose
Turn a finished Flow run's output directory into DataFrames, KPIs, Plotly
figures, and ResInsight 3D snapshot PNGs.

## Files
| File | Entry points | Notes |
|------|-------------|-------|
| `summary.py` | `read_summary(output_dir) -> DataFrame` | resfo-based; reads ESMRY if present, else UNSMRY+SMSPEC. Columns like `WOPR:PROD`, plus `TIME`. |
| `kpi.py` | `extract_kpis(df) -> dict` | Field totals (FOPT/FWPT/FGPT recovery), max watercut, final/avg GOR, plateau duration, producer count, breakthrough day. `_sanitize_kpis` replaces NaN/inf with None so json.dumps(allow_nan=False) never raises. Key names are a CONTRACT with frontend KPI cards (frontend/context.md table). |
| `plots.py` | `plot_production/plot_pressure/plot_cumulative/plot_watercut(df) -> go.Figure` | Per-producer traces with field fallback; watercut -0.0 sanitized. Serialized via `fig.to_json()` by the API; the frontend overrides paper/plot bgcolor + font color per UI theme, so do not rely on layout colors set here. |
| `resinsight_bridge.py` | `export_snapshots(output_dir) -> dict` | Shells out to `ResInsight --case X.EGRID --savesnapshots views` (batch CLI). NEVER raises; returns `{success, snapshots, error, duration_s}`. PNGs cached in `output_dir/resinsight_snapshots`. |

## Invariants
- The packaged ResInsight 2026.06 build has NO gRPC (verified by ldd/strace);
  `rips` can never connect. Batch CLI on a live display (`QT_QPA_PLATFORM=xcb`,
  DISPLAY set) is the only working path. Headless/offscreen segfaults. In
  Docker there is no display, so snapshots fail with a clean error string.
- `extract_kpis` output keys must not be renamed without updating the frontend
  KPI card table and `routes/results.py` consumers.

## Tests
`tests/unit/test_plots.py`, `tests/integration/test_resinsight_bridge.py`
(9 tests; live render skips without binary/DISPLAY/case).
