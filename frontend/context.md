# Frontend Context

## Stack
- **Framework**: React 18 + Vite 5 + TypeScript 5
- **Styling**: Tailwind CSS (dark blue palette: #0A1628, #0F2642, #00D9FF per UI_DESIGN_SPEC.md)
- **State**: Zustand with persist middleware (stores in `src/stores/useAppStore.ts`)
- **API Client**: Typed client in `src/api/client.ts` matching `opm_ai/api/schemas.py` DTOs
- **Editor**: Monaco Editor (@monaco-editor/react) with custom OPM language
- **Charts**: Plotly via plotly.js-dist-min
- **Build**: `NODE_OPTIONS=--max-old-space-size=4096 npm run build`

## Key Files
- `src/stores/useAppStore.ts` — Zustand slices: `useUIStore`, `useDeckStore`, `useSimulationStore`, `useChatStore`, `useSettingsStore`, `useLintStore`
- `src/api/client.ts` — Typed API client (REST + WebSocket) matching backend schemas
- `src/components/ResultsViewer.tsx` — KPI cards + Plotly charts + 3D placeholder
- `src/components/DeckBuilder.tsx` — Natural language → deck generation
- `src/components/DeckEditor.tsx` — Monaco editor with OPM syntax highlighting
- `src/components/SimulationRunner.tsx` — Job submission + live log streaming
- `src/components/LinterPanel.tsx` — Deck validation UI
- `src/components/ChatPanel.tsx` — LLM chat with tool calls
- `src/components/Sidebar.tsx`, `Header.tsx` — Navigation with SVG icons
- `src/components/SettingsPanel.tsx` — API keys + preferences. Stage C (2026-07-20): calls GET/POST `/api/settings` (via `api.getSettings`/`api.updateSettings`); provider + key-configured booleans come from the backend. Keys live in component state only, POSTed on save, cleared after: NOT in localStorage anymore. The zustand settings store still persists `llmProvider` for the Sidebar/Header/ChatPanel badges (synced from GET responses).
- `src/components/Home.tsx` — Dashboard with stats + quick actions

## KPI Card Keys (must match `opm_ai/postprocess/kpi.py::extract_kpis` output exactly)
| Key | Label | Unit | Format |
|-----|-------|------|--------|
| `days` | Simulation Days | days | `v.toFixed(0)` |
| `field_oil_recovery` | Cumulative Oil | STB | `v.toLocaleString()` |
| `field_water_recovery` | Cumulative Water | STB | `v.toLocaleString()` |
| `field_gas_recovery` | Cumulative Gas | MSCF | `v.toLocaleString()` |
| `max_watercut` | Max Water Cut | % | `(v*100).toFixed(1)` |
| `final_gor` | Final GOR | MSCF/STB | `v.toFixed(2)` |
| `producer_count` | Producers | — | `v.toFixed(0)` |
| `plateau_duration_days` | Plateau Duration | days | `v.toFixed(0)` |

**Units**: FIELD units (STB, MSCF, psia), NOT metric. The deck template uses FIELD units.

**Null handling**: `getKpiValue` returns plain ASCII `-` for undefined/null values (not em-dash).

## Dev Proxy
- Vite dev server (port 5173) proxies `/api` → `http://localhost:8000`
- Configured in `vite.config.ts`

## Prod Serving
- FastAPI serves `frontend/dist` at `/` via `StaticFiles`
- Built with `npm run build`. Needs ~3 GB of Node heap since `three` joined the
  bundle: `NODE_OPTIONS=--max-old-space-size=3000 npm run build`. It OOM-kills
  during minify on a 3 GB box with other processes resident; `--minify false`
  builds in less memory if it comes to that.

## 3D Viewer (`src/components/viewer3d/`)

Native WebGL grid viewer, no ResInsight process involved. The packaged
ResInsight build ships without gRPC and its batch mode needs a live X display,
so the viewer reads EGRID/INIT/UNRST server-side and streams binary blobs
instead. Binary rather than JSON: Norne is 6.2 MB of Float32 versus ~90 MB of
decimal text, and the buffer goes straight to WebGL unparsed.

| File | Role |
|---|---|
| `meshFormat.ts` | Parses the OPMG/OPMC/OPMP blobs. Pure, no three.js. Typed arrays are views onto the response buffer, not copies. |
| `colormaps.ts` | 14 ResInsight palettes (`RiaColorTables.cpp`), linear/log x continuous/discrete + category, ternary blend. |
| `engine.ts` | `Viewer3DEngine`: three.js scene, owns the canvas. Never imports React, never fetches. |
| `Grid3DViewer.tsx` | Default export, props `{ jobId }`. Owns all fetching and panel state, drives the engine. |
| `ControlPanel.tsx`, `LegendBar.tsx`, `HistogramBar.tsx`, `ResultInfoBox.tsx` | UI chrome. |

Binary layouts and endpoint contracts: `docs/3d-viewer-contract.md`. Do not
change a signature on one side without the other.

Three invariants worth knowing before editing:

- **The engine effect is keyed on `info`, not `[]`.** The component early-returns
  a loading tree until `/grid/info` lands, so the container div does not exist on
  first mount. An `[]`-effect bails there and never re-runs, and because every
  call site is `engine?.setX()`, the failure is silent: full UI, no canvas.
  Any new engine push effect must also list `engineGen` so a recreated engine
  gets the current state.
- **Viewer coordinates are the backend's**: origin subtracted, Z flipped up,
  origin always averaged over ACTIVE cells so "show inactive" cannot shift the
  model out from under the wells. Depth is `origin[2] - z`.
- **`jobId` changes reuse the component.** `ResultsViewer` mounts it without a
  `key`, so the grid-info effect must clear every piece of state that describes
  a specific cell or well (`picked`, `hovered`, `selectedWell`) alongside
  `info`. Anything new that names a cell index belongs in that reset, or it
  will survive into the next case and label the wrong cell.

`probe/` is a headless render harness for this component; see `probe/README.md`.
It exists because `tsc -b`, eslint and the backend suite all passed while the
viewer drew nothing.

## Future Work
- **Monaco Lint Squiggles**: Inline diagnostics from backend linter
- **Mobile**: Responsive sidebar + touch-friendly controls
- **3D Viewer**: intersections/section planes, contour maps, streamlines and
  multi-view linking are the remaining ResInsight 3D features not implemented.