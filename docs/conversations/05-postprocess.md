# Part 5 - Post-Processing, KPI Extraction & ResInsight Bridge
(module: `opm_ai.postprocess`)

> One-line purpose: Convert OPM Flow binary output (`.SMSPEC`/`.ESMRY`/`.UNSMRY`) into a labelled `pandas.DataFrame`, compute reservoir-engineering KPIs, build Plotly figures, and optionally drive ResInsight via `rips` for 3D snapshots.

---

## 1. Role in the AIM

This module is the *post-processing* layer of the OPM-AI workbench. After the runner produces simulation output, `postprocess` turns raw binary summary files into:

1. A tidy `DataFrame` with a `TIME` column and well/field vectors like `WOPT:PROD`, `FOPR`, `WBHP:PROD`.
2. A dictionary of **Key Performance Indicators** (ultimate recovery, water-cut breakthrough, plateau duration, sweep efficiency, etc.) that feeds the Part 7 explainer.
3. **Plotly figures** for production rates, pressures, water cut, cumulative production - ready for the React frontend.
4. An **optional ResInsight bridge** (`rips` gRPC on port 50051) that loads the case, creates summary plots, exports 3D saturation/pressure snapshots, and emits an HTML report.

Cross-references: 01-runner.md (produces the output dir), 07-explainer.md (consumes the KPI dict), 06-chat-and-api.md (`/api/results/{id}` returns JSON-serialised KPIs + Plotly JSON).

---

## 2. Position in Build Order

| Phase | Part | Depends on | Depended on by |
|-------|------|------------|----------------|
| 2 (v1.1) | 5 - Postprocess | 01-runner (`run_simulation`), `resfo` >= 5.0, `pandas`, `plotly` | 06-api (`/api/results`), 07-explainer (KPI dict), 08-deployment (Docker needs `rips`/`ResInsight`) |

Stage 4 in `IMPLEMENTATION_PLAN.md`. Gate: `pytest tests/unit/test_plots.py tests/integration/test_runner_spe1.py -v` passes.

---

## 3. Hard API Contract

Exact signatures asserted by the test suite.

### `read_summary(output_dir: Path) -> pd.DataFrame`
*File:* `tests/integration/test_runner_spe1.py::test_run_spe1_fixture`

```python
df = read_summary(result.output_dir)
assert "TIME" in df.columns
assert any("WOPT:PROD" in c for c in df.columns)   # well vector present
assert len(df) > 0
```

- Returns **empty DataFrame** (not `None`) if files missing/unreadable.
- Column names **must** follow `KEYWORD:WELL` pattern from ESMRY `KEYCHECK` (or reconstructed from SMSPEC `KEYWORDS` + `WGNAMES` + `NUMS`).
- `TIME` column in **days** (float).

### `extract_kpis(df: pd.DataFrame) -> dict[str, Any]`
*File:* `tests/integration/test_runner_spe1.py::test_run_spe1_fixture`

```python
kpis = extract_kpis(df)
assert "days" in kpis and kpis["days"] > 0
assert len(kpis) > 1           # at least days + one field KPI
```

Required keys (reservoir-engineer standard set):

| Key | Meaning | Notes |
|-----|---------|-------|
| `days` | Total simulation days | Always present, > 0 |
| `field_oil_recovery` | Cumulative oil (STB) | From `FOPT` or summed `WOPT:*` |
| `field_water_recovery` | Cumulative water (STB) | From `FWPT` |
| `field_gas_recovery` | Cumulative gas (MSCF) | From `FGPT` |
| `max_watercut` | Peak field water cut | Fraction 0-1 |
| `water_breakthrough_day` | First day WC > 1 % | `None` if never |
| `plateau_duration_days` | Days with oil rate >= 90 % of initial | 0 if no plateau |
| `avg_gor` | Average field GOR | `FGOR` mean |
| `sweep_efficiency` | Estimated volumetric sweep | Derived if pore-volume known |
| `producer_count` | Number of producing wells | From `WOPR:*` columns |
| Per-producer: `*_cum_oil`, `*_cum_water`, `*_cum_gas`, `*_final_bhp`, `*_max_watercut`, `*_final_watercut`, `*_avg_gor`, `*_final_gor` | | Prefix = well name |

### `plot_production(df: pd.DataFrame) -> plotly.graph_objects.Figure`
*File:* `tests/unit/test_plots.py::test_plot_production`, `test_plot_empty_dataframe`

```python
fig = plot_production(df)
assert len(fig.data) == 3          # FOPR, FWPR, FGPR traces when present
# Empty df:
fig = plot_production(pd.DataFrame())
assert len(fig.data) == 0
```

- **One trace per field rate vector present** (`FOPR`, `FWPR`, `FGPR`).
- If field totals absent, fall back to well-level (`WOPR:*`, `WWPR:*`, `WGPR:*`) with dashed lines.
- Empty DataFrame -> Figure with `len(fig.data) == 0`.

### `plot_pressure(df: pd.DataFrame) -> plotly.graph_objects.Figure`
*File:* `tests/unit/test_plots.py::test_plot_pressure`

```python
fig = plot_pressure(df)
assert len(fig.data) == 2   # WBHP:PROD, WBHP:INJ for SPE1
```

- **One trace per `WBHP:*` column**.

### `resinsight_bridge.py` - optional, guarded import
No tests yet; contract is operational (see section 6).

---

## 4. Key Design Decisions

| # | Decision | Rationale | Alternatives considered | Consequences |
|---|----------|-----------|-------------------------|--------------|
| 1 | **`resfo` (not `ecl2df`/`resdata`)** for summary reading | `BUILD_GUIDE.md` section 2 mandates `resfo` >= 5.0; it's the modern, maintained Rust/Python library; already in the system Python (`python3-opm-common`). | `ecl2df` (unmaintained), `resdata` (C++/Python, harder to install). | Column reconstruction logic lives in our code (section 4.2). |
| 2 | **Prefer ESMRY `KEYCHECK` for column names** | ESMRY is formatted ASCII; `KEYCHECK` vector already contains fully-qualified names like `"WBHP:INJ"`, `"WOPR:PROD"`. No need to reconstruct from SMSPEC. | Parse SMSPEC `KEYWORDS`/`WGNAMES`/`NUMS` always. | Simpler, less error-prone. SMSPEC path kept as fallback for UNSMRY-only runs. |
| 3 | **SMSPEC fallback reconstructs `KEYWORD:WELL` from `KEYWORDS` + `WGNAMES` + `NUMS`** | UNSMRY (binary) + SMSPEC is the classic pair; some decks only write UNSMRY. | Skip UNSMRY entirely. | Must handle placeholder `: +: +: +:` and `NUMS=0` (field totals). |
| 4 | **KPI set matches SPE/SPWLA practice** | Reservoir engineers expect: recovery, water-cut breakthrough, plateau, GOR, sweep. Tests only assert `days > 0` + `len(kpis) > 1`, but the dict is consumed by Part 7 explainer. | Minimal dict (`days` only). | Richer KPIs enable better LLM narratives; no test breakage. |
| 5 | **Plotly figures serialisable via `fig.to_json()`** | FastAPI returns `JSONResponse(fig.to_json())`; React `Plotly.react()` consumes it directly. | Return `dict` or custom spec. | Zero conversion layer in API. |
| 6 | **Empty DataFrame -> zero-trace Figure** | Matches `test_plot_empty_dataframe`; avoids frontend crashes. | Raise `ValueError`. | Graceful degradation. |
| 7 | **ResInsight bridge is optional / lazy-import** | ResInsight (`rips`) may not be installed in CI or minimal Docker. Module must import cleanly without it. | Hard dependency on `rips`. | `is_resinsight_available()` guard; Dockerfile installs ResInsight only in full image. |
| 8 | **ResInsight gRPC on 50051** | Verified in `Instructions.txt` GUIDE 4 and `OPM.md`. | HTTP REST. | `rips.Instance.find_or_start()` handles launch/connect. |

---

## 5. Toolchain Grounding

| Component | Path / Version | Verified |
|-----------|----------------|----------|
| `resfo` | 5.0.1 (system `python3-opm-common`) | verified `import resfo; resfo.__version__` |
| `pandas` | 2.x (venv) | verified |
| `plotly` | 5.x (venv) | verified |
| `rips` | System ResInsight 2024.x gRPC client | verified `import rips` works |
| ResInsight gRPC | Port **50051** (not 50051**0**) | verified `Instructions.txt` GUIDE 2/4 |
| OPM Flow summary files | SPE1 fixture: `.ESMRY`, `.SMSPEC`, `.UNSMRY` | verified `tests/fixtures/spe1/` |

**UNVERIFIED** (check at implementation time):
- Exact `rips` method names for `create_summary_plot`, `export_snapshot`, `export_html` - the `dir(rips)` dump shows `EclipseCase`, `SummaryPlot`, `EclipseView`, `Project.export_html`; verify signatures against ResInsight Python API docs.
- Whether `resfo.read()` on `.ESMRY` always returns `TSTEP` as integer days (SPE1 shows `TSTEP` = report-step indices; convert via `STARTDAT` if needed). Current code assumes `TSTEP` is already days.

---

## 6. Implementation Approach (ordered steps)

### 6.1 `summary.py` - `read_summary()`
1. **Find files**: `*.ESMRY` -> `*.UNSMRY` + `*.SMSPEC`.
2. **ESMRY path** (`_read_esmry`):
   - `resfo.read(path)` -> iterate `(keyword, array)`.
   - Collect `KEYCHECK` (decode bytes -> str), `TSTEP` (float days), `V0..Vn` vectors.
   - Map `V{i}` -> `KEYCHECK[i]` for column names.
   - Build `DataFrame({'TIME': tstep, **{col: vec}})`.
3. **UNSMRY+SMSPEC path** (`_read_unsmry_with_smspec`):
   - Parse SMSPEC for `KEYWORDS`, `WGNAMES`, `NUMS`, `UNITS`.
   - Read UNSMRY: group `SEQHDR`/`MINISTEP`/`PARAMS` triplets.
   - Stack `PARAMS` arrays -> `(n_vectors, n_steps)`.
   - Reconstruct column names via `_build_column_names()`.
4. Return empty `DataFrame` on any failure (never raise).

### 6.2 `kpi.py` - `extract_kpis(df)`
1. Guard: empty / no `TIME` -> `{"days": 0.0}`.
2. `days = float(df['TIME'].max())`.
3. Locate columns by prefix:
   - Field: `FOPR`, `FWPR`, `FGPR`, `FOPT`, `FWPT`, `FGPT`, `FGOR`, `WBHP`.
   - Well: `WOPR:*`, `WWPR:*`, `WGPR:*`, `WOPT:*`, `WWPT:*`, `WGPT:*`, `WBHP:*`.
4. Compute:
   - Recovery: last value of `FOPT`/`WOPT:*` sum.
   - Water cut: `FWPR / (FOPR + FWPR)` per step; breakthrough = first `WC > 0.01`.
   - Plateau: steps where `FOPR >= 0.9 * FOPR[0]`; duration = `max(TIME) - min(TIME)` in that mask.
   - GOR: `FGOR` mean / last; well GOR = `WGPR:* / WOPR:*`.
   - Per-well cumulatives & final BHP.
5. Return flat `dict` (JSON-serialisable).

### 6.3 `plots.py` - Plotly figures
1. `plot_production(df)`:
   - Empty -> `go.Figure()`.
   - For each of `FOPR`/`FWPR`/`FGPR` present -> `go.Scatter(x=TIME, y=df[col], mode='lines', name=pretty_name)`.
   - Fallback: well-level `WOPR:*` etc. with `line=dict(dash='dot')`.
   - Layout: title, axis labels, `hovermode='x unified'`, `template='plotly_white'`.
2. `plot_pressure(df)`:
   - One trace per `WBHP:*`.
3. (Optional helpers) `plot_cumulative`, `plot_watercut` - not contracted but useful for frontend.

### 6.4 `resinsight_bridge.py` - guarded optional
```python
_RIPS_AVAILABLE = False
try:
    import rips
    _RIPS_AVAILABLE = True
except ImportError:
    pass
```
Functions (all return `False`/`None`/`[]` if not available):
- `is_resinsight_available() -> bool`
- `load_case(deck_or_egrid: Path) -> rips.EclipseCase | None`
- `create_summary_plots(case, well_names: list[str] = None) -> list[rips.SummaryPlot]`
- `create_3d_snapshot(case, time_step: int, property: str, output_png: Path) -> bool`
- `export_case_html(case, output_html: Path) -> bool`
- `create_full_visualization_workflow(output_dir: Path, case_name: str) -> dict` - orchestrates the above, returns manifest with `snapshots`, `html_export`, etc.

### 6.5 `__init__.py` exports
```python
from .summary import read_summary
from .kpi import extract_kpis
from .plots import plot_production, plot_pressure, plot_cumulative, plot_watercut
from .resinsight_bridge import (
    is_resinsight_available, load_case, create_summary_plots,
    create_3d_snapshot, export_case_html, create_full_visualization_workflow
)
```

---

## 7. Risks & Open Questions

| Risk | Mitigation |
|------|------------|
| `resfo` API changes between 5.x and 6.x | Pin `resfo>=5.0,<6` in `pyproject.toml`; integration test covers SPE1. |
| ESMRY `TSTEP` not in days (some decks use step index) | Check `STARTDAT` + `TSTEP` conversion; add fallback to `RSTEP` if needed. |
| SMSPEC `WGNAMES` uses `: +: +: +:` placeholder inconsistently | Current code skips exact match; add regex `^:\+:\+:\+:\+$` for safety. |
| ResInsight `rips` method signatures differ from `dir()` dump | Verify at implementation; wrap in `try/except` and log. |
| Large UNSMRY (many time steps) -> memory blow in `np.array(all_vectors).T` | Stream-chunk if `len(all_vectors) > 10000`; not needed for SPE1-scale. |
| Plotly JSON size for many well traces | Frontend can request `well_subset`; backend filters columns. |

---

## 8. Verification & Done Criteria

| Criterion | Command |
|-----------|---------|
| Unit plots pass | `pytest tests/unit/test_plots.py -v` |
| SPE1 end-to-end: run -> summary -> KPIs | `pytest tests/integration/test_runner_spe1.py -v` |
| Linter unaffected | `pytest tests/unit/test_linter.py -v` |
| CLI build/run still works | `pytest tests/unit/test_cli.py -v` |
| Manual smoke: `python -c "from opm_ai.postprocess import read_summary, extract_kpis, plot_production; df=read_summary(Path('/tmp/test_flow')); print(df.shape, extract_kpis(df)['days']); fig=plot_production(df); print(len(fig.data))"` | Runs without error, prints `(123, 42) 3650.0 3` |

**Definition of Done**: All above commands pass; `opm_ai/postprocess/` has `context.md` (per CLAUDE.md folder rule); no `streamlit` imports anywhere.

---

## 9. Future Extensions

- **History matching metrics**: RMSE vs. observed rates, objective function value.
- **Uncertainty quantification**: ensemble statistics from multiple runs (P10/P50/P90 envelopes on plots).
- **ResInsight batch**: `rips` script mode for headless PNG/HTML generation in CI.
- **WebGL/Deck.gl export**: large 3D grids via `case.export_vtk()` + `vtkjs`.
- **PVT validation plots**: `plot_pvt()` comparing input tables vs. simulator tables.