# Task 11: Fix Plot Data Display + Dynamic Grid Layout + Per-Property Plotting + Unit Conversion

## Overview
The Results Viewer Plots tab shows empty plots because:
1. Main `/api/results/{job_id}` endpoint only returns `production` and `pressure` plots
2. ResultsViewer Plots tab expects `well_rates`, `well_cumulative`, `well_injection` from `/plot_group` endpoint
3. No dynamic grid layout (1×2, 2×2, 4×2 columns)
4. No option to plot one property per graph (e.g., oil rate for all wells on one graph)
5. No unit conversion (BBL vs m³ for oil, MSCF vs SM³ for gas)

## Files to Modify

### Frontend Changes
1. **`frontend/src/components/ResultsViewer.tsx`** - Main changes for grid, per-property, units
2. **`frontend/src/components/results/PlotCard.tsx`** - Support per-property mode
3. **`frontend/src/components/results/ResultsControlRail.tsx`** - Add grid layout selector, per-property toggle, unit selector
4. **`frontend/src/api/client.ts`** - Ensure proper API calls for plot_group
5. **`frontend/src/types.ts`** - Add types for new options

### Backend Changes
6. **`opm_ai/postprocess/plots.py`** - Add unit awareness (optional, just relabeling)
7. **`opm_ai/postprocess/plot_groups.py`** - Add per-property mode support

## Implementation Stages

### Stage 1: Type Definitions & API Client
- Add `GridLayout`, `UnitSystem`, `PerPropertyMode` types to `types.ts`
- Add `unitSystem` parameter to `plotGroup` API call
- Update `PlotGroupResponse` if needed

### Stage 2: Backend Plot Groups - Per-Property Mode
- Add `per_property` parameter to `plot_group` function in `plot_groups.py`
- When `per_property=True`, group traces by vector (e.g., WOPR) across all wells
- Return one figure per vector instead of one figure per group

### Stage 3: Backend Unit Awareness
- Add `unit_system` parameter to plotting functions
- Update axis labels based on unit system (FIELD: STB, MSCF, psia; METRIC: m³, SM³, bar)

### Stage 4: ResultsControlRail - New Controls
- Add grid layout selector (1col, 2col, 4col)
- Add per-property toggle
- Add unit system selector (FIELD/METRIC)
- Pass new state to ResultsViewer

### Stage 5: ResultsViewer - Main Logic
- Add state for grid layout, per-property mode, unit system
- Fetch plots via `/plot_group` endpoint when selections change
- When per-property mode is on: group by vector, show one PlotCard per vector with all wells
- When per-property mode is off: group by vector family (current behavior)
- Implement dynamic grid layout (CSS Grid)

### Stage 6: PlotCard - Per-Property Support
- Accept new props for per-property mode
- Display vector name in title when in per-property mode

### Stage 7: Tests
- Add/update frontend tests for new functionality
- Test per-property mode
- Test grid layouts
- Test unit conversion labels

## Success Criteria
1. Plots show actual data from `/plot_group` endpoint
2. Grid layout selector works (1×2, 2×2, 4×2)
3. Per-property toggle works - shows one vector across all wells
4. Unit system toggle changes axis labels (STB↔m³, MSCF↔SM³, psia↔bar)
5. All existing functionality still works
6. Tests pass