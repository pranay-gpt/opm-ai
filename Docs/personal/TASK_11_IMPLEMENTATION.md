# Task 11 Implementation: Fix Plots + Dynamic Grid + Per-Property + Unit Conversion

**Date:** August 2026  
**Status:** Complete ✅  
**Branch:** main  

---

## Overview

Task 11 implemented four major features for the OPM-AI Results page:

1. **Fixed plot data display** — Root cause was SMSPEC keyword parsing (trailing spaces)
2. **Dynamic grid layout** — 3 options: 1 column, 2 columns, 4 columns
3. **Per-property plotting** — One graph per vector across all wells
4. **Unit conversion** — FIELD (BBL/STB/psia) ↔ METRIC (m³/SM³/bar) axis relabeling

---

## Files Modified

### Backend (`opm_ai/postprocess/`)

| File | Changes |
|------|---------|
| `summary.py` | Fixed SMSPEC keyword matching — `kw.strip()` before comparing to `('KEYWORDS', 'WGNAMES', 'NAMES', 'NUMS', 'UNITS')` |
| `plot_groups.py` | Added `_VECTOR_LABELS` dict, `unit_system` param to all plot functions, per-property mode helpers, human-readable trace names |

### API (`opm_ai/api/routes/`)

| File | Changes |
|------|---------|
| `results.py` | Pass `unit_system` and `per_property` to `build_plot_group()` |

### Frontend (`frontend/src/`)

| File | Changes |
|------|---------|
| `types.ts` | Added `VECTOR_LABELS` export, `GridLayout`, `UnitSystem` types |
| `api/client.ts` | Added `per_property` parameter to `plotGroup()` |
| `components/results/ResultsControlRail.tsx` | New UI: Grid selector (1/2/4 col), Per-property toggle, Unit system selector; uses `VECTOR_LABELS` for display |
| `components/ResultsViewer.tsx` | Dynamic CSS grid rendering based on `gridLayout`, per-property fetch logic |

---

## Technical Details

### 1. Plot Data Fix (summary.py)

**Root Cause:** SMSPEC keywords had trailing spaces (`'KEYWORDS '` vs `'KEYWORDS'`). The `resfo.read()` returns keys with padding.

**Fix:** Strip keywords before matching:
```python
for kw, arr in smspec_data:
    kw_stripped = kw.strip()
    if kw_stripped in ('KEYWORDS', 'WGNAMES', 'NAMES', 'NUMS', 'UNITS'):
        ...
        metadata[kw_stripped] = arr
```

**Also fixed UNSMRY parsing** — same issue with `'SEQHDR  '`, `'MINISTEP'`, `'PARAMS  '`.

### 2. Vector Labels (Human-Readable Names)

Added `_VECTOR_LABELS` dictionary mapping short codes to display names:

| Short Code | Display Name | Context |
|------------|--------------|---------|
| FOPR / WOPR | Oil Rate | Field/Well rates |
| FWPR / WWPR | Water Rate | Field/Well rates |
| FGPR / WGPR | Gas Rate | Field/Well rates |
| WBHP | BHP | Well rates |
| WGOR | GOR | Well rates |
| WWCT | Water Cut | Well rates |
| FOPT / WOPT | Oil Cumulative | Field/Well cumulative |
| FWPT / WWPT | Water Cumulative | Field/Well cumulative |
| FGPT / WGPT | Gas Cumulative | Field/Well cumulative |
| FWCT | Water Cut | Field derived |
| FGOR | GOR | Field derived |
| FPR | Avg Pressure | Field derived |
| WGIR | Gas Injection Rate | Well injection |
| WWIR | Water Injection Rate | Well injection |
| WOIR | Oil Injection Rate | Well injection |
| WGIT | Gas Injection Cumulative | Well injection |
| WWIT | Water Injection Cumulative | Well injection |

**Usage:**
- Frontend: `VECTOR_LABELS[vec] || vec` in ResultsControlRail checkboxes
- Backend: `_VECTOR_LABELS.get(kw, kw)` in plot titles, trace names, axis labels

### 3. Per-Property Mode

When `per_property=true`, the API returns **one figure per vector** instead of one figure per group.

**API Change:**
```python
# /api/results/{job_id}/plot_group/{group}?per_property=true&vectors=WOPR,WGPR
# Returns: [fig1_json, fig2_json, ...]  (array of Plotly figures)
```

**Backend logic** (`_well_figure_per_property`, `_field_figure_per_property`):
- Groups traces by vector keyword across all wells
- Each figure: `title = "{Group} - {Vector Label}"`, Y-axis = vector label with units
- Example: "Well Rates - Oil Rate" (STB/day), "Well Rates - Gas Rate" (MSCF/day)

### 4. Dynamic Grid Layout

**Frontend state:** `gridLayout: '1col' | '2col' | '4col'`

**CSS Grid:**
```tsx
<div className={`
  grid gap-4
  ${gridLayout === '1col' ? 'grid-cols-1' : ''}
  ${gridLayout === '2col' ? 'grid-cols-1 md:grid-cols-2' : ''}
  ${gridLayout === '4col' ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4' : ''}
`}>
  {figures.map(...)}
</div>
```

**Responsive breakpoints:**
- 1col: Always 1 column
- 2col: 1 on mobile (<768px), 2 on desktop
- 4col: 1 on mobile, 2 on tablet, 4 on large desktop

### 5. Unit System

**Backend:** `unit_system: 'FIELD' | 'METRIC'` — changes **axis labels only**, no value conversion.

**Label mapping** (`_UNIT_LABELS`):
| Category | FIELD | METRIC |
|----------|-------|--------|
| Oil rate | STB/day | m³/day |
| Water rate | STB/day | m³/day |
| Gas rate | MSCF/day | SM³/day |
| Oil cumulative | STB | m³ |
| Water cumulative | STB | m³ |
| Gas cumulative | MSCF | SM³ |
| Pressure | psia | bar |
| Generic rate | Rate | Rate |
| Generic cumulative | Cumulative Volume | Cumulative Volume |

**Applied to:** Y-axis titles, trace hover templates, figure titles.

---

## Testing

### Backend Tests (`tests/unit/test_plot_groups.py`)
All 16 tests pass:
- Field groups: rates, cumulative, derived
- Well groups: rates, cumulative, injection
- Edge cases: empty DF, missing vectors, single timestep
- Dispatch and log scale

### Integration Tests (`tests/integration/`)
All 17 tests pass:
- Plot success/failure shapes
- Categories endpoint
- CSV export (native, monthly, yearly)
- Chat tools validation

### Frontend Tests (`frontend/src/components/results/`)
All 20 tests pass:
- ResultsViewer rendering
- ResultsControlRail interactions

### TypeScript
Clean compilation: `npx tsc -b` — no errors.

---

## API Examples

### Import Results
```bash
curl -X POST http://localhost:8000/api/imported-results \
  -F "files=@SPE1CASE1.SMSPEC" \
  -F "files=@SPE1CASE1.UNSMRY"
# → {"job_id": "abc123", ...}
```

### Get Categories
```bash
curl http://localhost:8000/api/results/abc123/categories
# → {"well_rates": {"PROD": ["WOPR", "WGPR", ...]}, ...}
```

### Plot Regular (one figure per group)
```bash
curl "http://localhost:8000/api/results/abc123/plot_group/well_rates?wells=PROD&vectors=WOPR,WGPR&unit_system=field"
# → Single Plotly figure with traces: "Oil Rate PROD", "Gas Rate PROD"
```

### Plot Per-Property (one figure per vector)
```bash
curl "http://localhost:8000/api/results/abc123/plot_group/well_rates?wells=PROD&vectors=WOPR,WGPR&unit_system=field&per_property=true"
# → Array of 2 figures:
#   Fig 0: "Well Rates - Oil Rate", Y: "Oil Rate (STB/day)"
#   Fig 1: "Well Rates - Gas Rate", Y: "Gas Rate (MSCF/day)"
```

### Metric Units
```bash
curl "http://localhost:8000/api/results/abc123/plot_group/well_rates?wells=PROD&vectors=WOPR&unit_system=metric"
# → Y-axis: "Rate (m³/day)"
```

---

## UI Screenshots (Described)

### ResultsControlRail (Left Panel)
```
┌─────────────────────────────────────┐
│ ▼ Producers                         │
│   ☑ PROD                            │
├─────────────────────────────────────┤
│ ▼ Injectors                         │
│   ☑ INJ                             │
├─────────────────────────────────────┤
│ ▼ Vector Groups                     │
│   ▼ Field Rates                     │
│     ☑ Oil Rate                      │
│     ☐ Water Rate                    │
│   ▼ Well Rates                      │
│     ☑ Oil Rate                      │
│     ☑ Gas Rate                      │
│     ☑ BHP                           │
├─────────────────────────────────────┤
│ ▼ Display                           │
│   ☐ Log scale (Y)                   │
├─────────────────────────────────────┤
│ ▼ Layout                            │
│   Grid Columns: [2 columns ▼]       │
│   ☑ Per-property (one vector/graph) │
│   Unit System: [Field ▼]            │
└─────────────────────────────────────┘
```

### ResultsViewer (Right Panel) — Grid Layout
- **1col:** Single column, full width plots
- **2col:** Two plots side-by-side on desktop, stacked on mobile
- **4col:** Four plots in 2×2 grid on desktop, 2×2 on tablet, stacked on mobile

---

## Known Limitations / Future Work

1. **No value conversion** — Unit system only changes labels. True conversion would need PVT-aware math.
2. **Per-property for field groups** — Works but field groups typically have 1-3 vectors anyway.
3. **No persistence** — Grid layout, per-property, unit system reset on page reload. Could add localStorage.
4. **Hover template** — Still shows short code in some hover templates (e.g., "WOPR PROD: 50"). Could use labels there too.

---

## Rollback / Debugging

If issues arise:

```bash
# Check backend health
curl http://localhost:8000/health

# Check summary parsing
python3 -c "
from pathlib import Path
from opm_ai.postprocess.summary import read_summary
df = read_summary(Path('/tmp/opm_ai_imported_xxx'))
print(df.shape, list(df.columns)[:5])
"

# Check plot generation
python3 -c "
from opm_ai.postprocess.plot_groups import plot_well_rates
import pandas as pd
df = pd.DataFrame({'TIME': [1,2], 'WOPR:PROD': [50,40]})
fig = plot_well_rates(df, ['PROD'], unit_system='FIELD')
print(fig.layout.title.text, fig.layout.yaxis.title.text)
"
```

---

## Related Documentation

- `IMPLEMENTATION_PLAN.md` — Overall project plan
- `docs/3d-viewer-contract.md` — 3D viewer types (shared types.ts)
- `06-chat-and-api.md` — API contract reference

---

**End of Task 11 Documentation**