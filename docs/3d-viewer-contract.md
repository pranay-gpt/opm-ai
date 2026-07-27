# 3D Viewer: API and module contract

Authoritative interface between the backend grid endpoints, the WebGL engine,
and the React UI. All three are built in parallel against this document; do
not change a signature here without updating the other side.

Backing modules that already exist and are verified:

- `opm_ai/postprocess/grid3d.py` — `EclipseGrid`, corner-point geometry,
  properties, time steps, faults, NNCs, `derive_soil`, `statistics`.
- `opm_ai/postprocess/grid_mesh.py` — `build_surface`, `build_edges`,
  `pack_mesh`, `pack_values`, `visible_faces`, `MESH_FORMAT_VERSION`.

Verified against `tests/fixtures`: SPE1 (10x10x3 cartesian, FIELD) and Norne
(46x112x22 corner-point with faults, 44431 active cells, METRIC). Norne meshes
to 36324 quads / 6.2 MB in ~0.2 s.

---

## 1. HTTP endpoints

All under `/api/results/{job_id}/grid`. Every endpoint resolves the job's
output directory with the existing `_completed_job_output_dir(job_id)` helper
in `opm_ai/api/routes/results.py` (404 unknown job, 400 not completed).
If the directory holds no `.EGRID`, return **404** with a clear detail string.
If the grid cannot be parsed, return **422** with the `GridError` message.

### GET `/api/results/{job_id}/grid/info` → JSON `GridInfoResponse`

```jsonc
{
  "nx": 46, "ny": 112, "nz": 22,
  "active_cells": 44431, "total_cells": 113344,
  "unit_system": "METRIC",          // "" when unknown
  "length_unit": "m",               // ft | m | cm
  "origin": [453000.0, 7320000.0, -2600.0],   // subtracted before float32
  "bbox": { "min": [-1234.5, -2345.6, -180.2], "max": [1234.5, 2345.6, 180.2] },
  "static_properties": ["PORO", "PERMX", ...],   // ordered, preferred first
  "dynamic_properties": ["PRESSURE", "SGAS", "SWAT", "SOIL", "RS", ...],
  "derived_properties": ["SOIL"],   // subset of dynamic that we compute
  "time_steps": [ { "index": 0, "report": 0, "days": 0.0, "date": "1997-11-06" } ],
  "fault_face_count": 17720,
  "nnc_count": 15349,
  "has_wells": true
}
```

`bbox` is in **viewer coordinates**: origin already subtracted and Z negated
so +Z is up. It is the box of the drawn (active) cells.

`dynamic_properties` includes `SOIL` whenever SWAT or SGAS is present, since
we derive it exactly as ResInsight does (`1 - SWAT - SGAS - SSOL`).
`TERNARY` is **not** listed as a property; it is a UI display mode that pulls
SOIL/SGAS/SWAT itself.

### GET `/api/results/{job_id}/grid/mesh?include_inactive=false` → binary

`Content-Type: application/octet-stream`. Body is exactly `pack_mesh(...)`
output. Little-endian throughout:

| offset | type | meaning |
|---|---|---|
| 0 | 4 bytes | magic `OPMG` |
| 4 | uint32 | format version (`MESH_FORMAT_VERSION`, currently 1) |
| 8 | uint32 | `n_vertices` |
| 12 | uint32 | `n_indices` (triangle corners = ntris*3) |
| 16 | uint32 | `n_edges` (line endpoints = nsegs*2) |
| 20 | 3 x float64 | `origin` (x, y, z) |
| 44 | n_vertices*3 float32 | positions, Z up, origin subtracted |
| … | n_vertices*3 float32 | normals |
| … | n_vertices int32 | active cell index per vertex |
| … | n_vertices uint8 | face id per vertex (0=I- 1=I+ 2=J- 3=J+ 4=K- 5=K+), **padded to a 4-byte boundary** |
| … | n_indices uint32 | triangle indices |
| … | n_edges uint32 | edge line indices |

Cache the packed blob per `(job_id, include_inactive)`; it is deterministic.
Serve with `ETag` and honour `If-None-Match` with a 304.

### GET `/api/results/{job_id}/grid/cells` → binary

Per-active-cell companion to the mesh. The mesh carries only a flat active-cell
index, so without this the client cannot range-filter on I/J/K, label a pick
with i,j,k, shade fault faces, or draw NNCs. Body is `pack_cells(...)` output,
little-endian throughout:

| offset | type | meaning |
|---|---|---|
| 0 | 4 bytes | magic `OPMC` |
| 4 | uint32 | format version (`CELLS_FORMAT_VERSION`, currently 1) |
| 8 | uint32 | `n_cells` (= `active_cells` from `/grid/info`) |
| 12 | uint32 | `n_nncs` (= `nnc_count` from `/grid/info`) |
| 16 | 3 x float64 | `origin` (x, y, z) — byte-identical to the mesh's |
| 40 | n_cells*3 int32 | zero-based i, j, k per active cell |
| … | n_cells*3 float32 | cell centroid, **viewer coords** (origin subtracted, Z flipped) |
| … | n_cells*6 uint8 | fault flag per face, order I- I+ J- J+ K- K+, **padded to a 4-byte boundary** |
| … | n_nncs*2 int32 | active-cell index pairs |

Centres go through `grid_mesh.to_viewer(grid.cell_centres(), surface_origin(grid))`
— the same two helpers `build_surface` uses — so every centre lands inside its
own meshed cell. Do not recompute the shift anywhere else.

The fault mask is per **cell x face**, not per drawn quad: the quad set depends
on `include_inactive`, while `(cell, face)` does not, so one blob serves both
mesh variants. The client expands it with `expandFaultMask(mesh, faultFaces)`,
which reads `cellIds[4q]` and `faceIds[4q]` off the mesh and therefore makes no
assumption about the order `build_surface` emitted quads in.

Independent of `include_inactive`, so the client fetches it once per job.
Cached per `(job_id)` with the EGRID mtime in the key; served with `ETag` and
honours `If-None-Match` with a 304, like `/grid/mesh`.

### GET `/api/results/{job_id}/grid/property?name=SOIL&step=0` → binary

`step` is ignored for static properties. Body:

| offset | type | meaning |
|---|---|---|
| 0 | 4 bytes | magic `OPMP` |
| 4 | uint32 | version (1) |
| 8 | uint32 | `json_len` |
| 12 | json_len bytes | UTF-8 JSON metadata, **padded to a 4-byte boundary** |
| … | n_active float32 | one value per active cell, grid order |

JSON metadata:

```jsonc
{
  "name": "SOIL", "step": 0, "count": 44431,
  "kind": "dynamic",              // static | dynamic | derived
  "categorical": false,           // true for SATNUM/FIPNUM/... -> category legend
  "unit": "",                     // best-effort, "" when unknown
  "min": 0.0, "max": 0.82, "mean": 0.41, "p10": 0.77, "p90": 0.05,
  "sum": 1.8e4, "count_finite": 44431,
  "histogram": [ ... 50 ints ... ], "bin_edges": [ ... 51 floats ... ]
}
```

Statistics come from `grid3d.statistics()` (p10 = value exceeded by 10% of
cells, matching ResInsight). 404 when the property name is unknown for this
case, 400 when `step` is out of range.

### GET `/api/results/{job_id}/grid/property/range?name=PRESSURE` → JSON

Global range over **all** time steps, for the "auto range, all time steps"
legend mode. Scans the restart file once and caches per `(job_id, name)`.

```jsonc
{ "name": "PRESSURE", "min": 170.2, "max": 331.9, "steps_scanned": 65 }
```

For a static property this equals its single-step range.

### GET `/api/results/{job_id}/grid/wells?step=0` → JSON `WellsResponse`

```jsonc
{
  "step": 0,
  "wells": [
    {
      "name": "C-4H",
      "type": "producer",            // producer | oil_injector | gas_injector | water_injector | unknown
      "head": [x, y, z],             // viewer coords, top of the trajectory
      "i": 10, "j": 34, "k": 6,      // zero-based head cell
      "trajectory": [[x,y,z], ...],  // viewer coords, ordered head -> toe
      "completions": [
        { "i": 10, "j": 34, "k": 6, "cell": 12345, "center": [x,y,z], "open": true }
      ]
    }
  ]
}
```

Coordinates use the **same origin and Z flip as the mesh**, so wells and grid
line up without further transformation on the client.

---

## 2. Frontend module boundary

Directory `frontend/src/components/viewer3d/`.

### `meshFormat.ts` — pure parsing, no three.js

```ts
export interface ParsedMesh {
  version: number;
  origin: [number, number, number];
  positions: Float32Array;   // n*3
  normals: Float32Array;     // n*3
  cellIds: Int32Array;       // n
  faceIds: Uint8Array;       // n
  indices: Uint32Array;
  edges: Uint32Array;
  vertexCount: number;
}
export function parseMesh(buf: ArrayBuffer): ParsedMesh;

export interface ParsedCells {
  version: number;
  origin: [number, number, number];
  ijk: Int32Array;           // n_cells*3, zero-based
  centers: Float32Array;     // n_cells*3, viewer coords
  faultFaces: Uint8Array;    // n_cells*6, face order I- I+ J- J+ K- K+
  nnc: Int32Array;           // n_nncs*2, active-cell index pairs
  cellCount: number;
  nncCount: number;
}
export function parseCells(buf: ArrayBuffer): ParsedCells;

/** Per-cell x per-face fault flags -> the per-quad mask setFaultMask wants. */
export function expandFaultMask(mesh: ParsedMesh, faultFaces: Uint8Array): Uint8Array;

export interface PropertyStats {
  name: string; step: number; count: number;
  kind: 'static' | 'dynamic' | 'derived';
  categorical: boolean; unit: string;
  min: number; max: number; mean: number; p10: number; p90: number;
  sum: number; count_finite: number;
  histogram: number[]; bin_edges: number[];
}
export interface ParsedProperty { stats: PropertyStats; values: Float32Array }
export function parseProperty(buf: ArrayBuffer): ParsedProperty;
```

Both throw `Error` with a readable message on a bad magic or version.

### `colormaps.ts` — palettes and scalar-to-colour mapping

```ts
export type PaletteName =
  | 'normal' | 'opposite_normal' | 'black_white' | 'white_black'
  | 'blue_white_red' | 'red_white_blue' | 'angular' | 'rainbow'
  | 'stimplan' | 'heat_map' | 'green_red' | 'blue_magenta'
  | 'category' | 'contrast_category';

export type MappingType =
  | 'linear_continuous' | 'linear_discrete'
  | 'log_continuous' | 'log_discrete' | 'category';

export interface ColorMapping {
  palette: PaletteName;
  mapping: MappingType;
  levels: number;        // bands for the *_discrete modes
  min: number; max: number;
  invert: boolean;
  undefinedColor: [number, number, number];
}

/** Fill an RGB Float32Array (n*3, values 0..1) from per-cell values. */
export function mapColors(
  values: Float32Array, cellIds: Int32Array, m: ColorMapping, out: Float32Array
): void;

/** Ternary saturation blend: R=SGAS, G=SOIL, B=SWAT, as ResInsight does. */
export function mapTernary(
  soil: Float32Array, sgas: Float32Array, swat: Float32Array,
  cellIds: Int32Array, ranges: TernaryRanges, out: Float32Array
): void;

/** Evenly spaced legend swatches for the current mapping. */
export function legendStops(m: ColorMapping, n: number):
  Array<{ value: number; color: string }>;
```

Palette RGB stops are taken from ResInsight `RiaColorTables.cpp`; `normal` is
blue → cyan → green → yellow → red, and the two category palettes are the 21
Kelly colours.

### `engine.ts` — three.js scene, owns the canvas, no React

```ts
export interface CellInfo {
  activeIndex: number;
  i: number; j: number; k: number;           // zero-based
  center: [number, number, number];          // viewer coords
  depth: number;                             // positive down, grid units
  faceId: number; faceName: string;
  point: [number, number, number];           // exact hit point
}

export interface CellFilter {
  iMin: number; iMax: number;                // inclusive, zero-based
  jMin: number; jMax: number;
  kMin: number; kMax: number;
  propertyRange: { min: number; max: number; exclude: boolean } | null;
  hiddenCells: Int32Array | null;            // explicit hide list
}

export interface DisplayOptions {
  surfaceMode: 'surface' | 'faults_only' | 'none';
  meshMode: 'full' | 'faults_only' | 'none';
  showInactive: boolean;
  zScale: number;                            // vertical exaggeration
  background: string;                        // css colour
  lighting: boolean;
  opacity: number;                           // 0..1
  showAxes: boolean;
  showGridBox: boolean;
  showWells: boolean;
  showWellLabels: boolean;
  showNncs: boolean;
  perspective: boolean;
  edgeColor: string;
}

export class Viewer3DEngine {
  constructor(canvas: HTMLCanvasElement);
  setMesh(mesh: ParsedMesh): void;
  setColors(rgb: Float32Array): void;         // n*3, per vertex, 0..1
  setValues(values: Float32Array | null): void; // for property filtering
  setDisplay(opts: Partial<DisplayOptions>): void;
  setFilter(filter: CellFilter): void;
  setWells(wells: Well[]): void;
  setFaultMask(isFault: Uint8Array | null): void;   // per quad, or per vertex
  setCellIjk(ijk: Int32Array): void;                // n_cells*3, after setMesh
  setNncs(pairs: Int32Array, centers: Float32Array): void;
  focusWell(name: string | null): void;             // frame it, dim the others
  onPick(cb: (info: CellInfo | null) => void): void;
  onHover(cb: (info: CellInfo | null) => void): void;
  viewAlong(axis: '+x' | '-x' | '+y' | '-y' | '+z' | '-z'): void;
  zoomAll(): void;
  screenshot(): string;                       // data URL, PNG
  resize(): void;
  dispose(): void;
}
```

The engine never imports React and never fetches. The UI owns all state and
pushes it down; the engine only reports picks and hovers back up.

### `Grid3DViewer.tsx` — the React component

Default export, props `{ jobId: string }`. Owns fetching, all panel state, and
drives the engine. This is what `ResultsViewer.tsx` renders in its "3D View"
tab, replacing the placeholder.

---

## 3. Conventions to follow

- Backend: routes stay thin adapters; heavy work goes in `opm_ai/postprocess/`
  and runs in a thread executor (`run_in_executor`) so the event loop is free.
- Never raise out of a route for an expected condition — return a clear
  HTTPException with a useful `detail`.
- Frontend: Tailwind classes already in `index.css` (`card`, `panel-header`,
  `panel-title`, `btn-primary`, `tab`, `badge`). Theme via `useResolvedTheme()`
  from `../../stores/useAppStore`; dark and light must both look right.
- No new npm dependency beyond `three` / `@types/three`, already installed.
- TypeScript must pass `tsc -b` with the repo's existing strictness.
