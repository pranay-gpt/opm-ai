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
- Built with `npm run build` (requires 4GB Node heap)

## Future Work
- **3D Viewer**: ResInsight headless gRPC bridge (Phase 2)
- **Monaco Lint Squiggles**: Inline diagnostics from backend linter
- **Mobile**: Responsive sidebar + touch-friendly controls