# opm_ai/postprocess - Simulation output readers

## Module Purpose

Turns OPM Flow output files into things a UI can show: summary vectors and
KPIs, Plotly figures, and the corner-point geometry the interactive 3D viewer
renders. Nothing here shells out to a simulator; everything reads files that
a completed run left behind.

## File Map

| File | Purpose |
|------|---------|
| `summary.py` | UNSMRY/ESMRY -> pandas DataFrame of summary vectors |
| `kpi.py` | Summary DataFrame -> NaN-sanitised KPI dict |
| `plots.py` | Production and pressure Plotly figures |
| `grid3d.py` | `EclipseGrid`: EGRID/INIT/UNRST -> corner geometry, properties, time steps, faults, NNCs, wells |
| `grid_mesh.py` | Visible-face culling, triangulation, binary mesh/value packing |
| `resinsight_bridge.py` | ResInsight batch-CLI PNG snapshots (legacy; needs a live X display) |

## Key Invariants

### 1. Corner order and depth sign (`grid3d.py`)

`corners()` returns shape `(nz, ny, nx, 8, 3)` in ECLIPSE corner order,
`e = kk*4 + jj*2 + ii`, in **raw grid coordinates with depth positive
downward**. The regression check that pins this down is that
`cell_centres()[:, 2]` reproduces the INIT `DEPTH` array: exactly on SPE1,
within 1e-3 on Norne. If the corner bit order or the pillar interpolation
were wrong, that agreement would collapse and nothing else would necessarily
notice. Do not "clean up" the sign here; flipping happens only on export.

### 2. One coordinate transform, one origin (`grid_mesh.py`)

`surface_origin(grid)` and `to_viewer(points, origin)` are the only place the
export transform (subtract origin, negate Z) is spelled out. `build_surface`
uses them for vertices and `routes/grid.py` uses them for well trajectories,
which is what keeps wells registered with the grid.

`surface_origin` is deliberately computed from the **active** cells only,
never from the drawn set. If it were the mean of the drawn cells it would move
when the viewer toggles "show inactive cells" (on Norne by 276 m in X), and
the model would jump while the wells stayed put. Test:
`test_origin_is_independent_of_include_inactive`.

### 3. Binary layouts are a cross-language contract

`pack_mesh` (`OPMG`) and the `OPMP` property blob assembled in
`api/routes/grid.py` are parsed by
`frontend/src/components/viewer3d/meshFormat.ts`. Both are documented in
`docs/3d-viewer-contract.md` and both pad their variable-length byte sections
to a 4-byte boundary so the following typed arrays stay aligned. Change the
layout only by bumping `MESH_FORMAT_VERSION` (which is part of the route's
cache key) and updating the TypeScript parser in the same commit.

### 4. Restart well record layout (`grid3d.wells`)

Verified empirically against Norne's UNRST, not taken on trust. Record
lengths come from INTEHEAD and are cross-checked against actual array sizes:
`nwells = INTEHEAD[16]`, `ncwmax = [17]`, `niwelz = [24]`, `nzwelz = [27]`,
`niconz = [32]`.

- Well name: `ZWEL[w * nzwelz]`, decoded and stripped.
- IWEL record: index 0/1/2 = head I/J/K (one-based), 4 = connection count,
  6 = well type (1 producer, 2 oil inj, 3 water inj, 4 gas inj).
- ICON record: index 0 = connection index (<= 0 means an unused slot),
  1/2/3 = I/J/K (one-based), 5 = status (> 0 open).

The well **count grows over the history**: Norne has 3 wells at step 0 and 36
at step 64, and SPE1 has 0 at step 0 and 2 later. An empty well list is a
normal answer, not an error. Everything that fails to validate degrades
(drop the completion, drop the trajectory) rather than emitting garbage
coordinates.

### 5. One pass per file

`read_dynamic_many`, `dynamic_range` and `soil_range` exist so that deriving
SOIL or scanning a global range walks the UNRST once rather than once per
keyword. `soil_range` recombines SWAT/SGAS **per step**, because
`1 - min(SWAT) - min(SGAS)` taken across different steps is not a value any
cell ever held.

## Future Plan

1. **NNC rendering** — `nnc_pairs()` is exposed but the viewer does not draw
   the connections yet.
2. **LGRs** — `EclipseGrid` reads the root grid only; LGR keywords are in
   `_NON_CELL_KEYWORDS` and silently skipped.
3. **Flow diagnostics** — TOF / drainage volumes would need the NNC
   transmissibilities from `TRANNNC`, also currently skipped.
4. **Retire `resinsight_bridge.py`** — the packaged ResInsight has no gRPC and
   its snapshots need a live X display, which is why the WebGL viewer exists.
   Keep it only until the 3D viewer covers the same screenshots.
