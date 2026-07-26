# Frontend Context

Last updated: 2026-07-22 (theme system + navigation + review-hardening overhaul).

## Stack
- **Framework**: React 18 + Vite 5 + TypeScript 5, react-router-dom v6 (BrowserRouter)
- **Styling**: Tailwind CSS 3.4 over CSS custom properties (see Theme System below)
- **State**: Zustand v5 with persist middleware (`src/stores/useAppStore.ts`)
- **API Client**: Typed client in `src/api/client.ts` matching `opm_ai/api/schemas.py` DTOs
- **Editor**: Monaco (@monaco-editor/react), custom OPM language, `opm-dark`/`opm-light` themes
- **Charts**: Plotly via plotly.js-dist-min (layout restyled client-side per theme)
- **Build**: `NODE_OPTIONS=--max-old-space-size=2048 npx vite build` (sourcemaps OFF;
  on this 3GB host stop uvicorn first or the build gets OOM-killed)

## Theme System (2026-07-22)
- Palette lives as RGB-triplet CSS vars in `src/index.css` (`--c-base: 8 16 40` style),
  so Tailwind opacity modifiers (`bg-primary/20`) work. Dark is `:root` default;
  light is `[data-theme="light"]`; auto is a `prefers-color-scheme` media block
  scoped to `:root:not([data-theme])`. The light palette is intentionally duplicated
  in the auto block: keep both copies in sync when editing colors.
- `tailwind.config.js` maps color names to those vars. **The page-background color
  key is `page`, NOT `base`**: `text-base` must stay Tailwind's font-size utility
  (a `base` color key generated a colliding `.text-base` color rule that also broke
  button font sizes). Use `bg-page` / `text-page`.
- Toggle: Header (Auto/Light/Dark) -> `useUIStore.setTheme`, persisted in
  localStorage key `opm-ai-ui`. `ThemeApplier` in App.tsx sets/removes the
  `data-theme` attribute. A pre-paint inline script in `index.html` reads the same
  localStorage key to prevent a dark flash on load - keep key name and shape in sync.
- Embedded widgets can't read CSS vars: use `useResolvedTheme()` from the store
  (collapses 'auto' via matchMedia, subscribes to system changes). Monaco editors
  pick `opm-light`/`light` vs `opm-dark`/`vs-dark`; ResultsViewer's PlotCard
  overrides Plotly layout (transparent backgrounds + theme font color).
- Design language: sharp major elements (cards/inputs/panels `rounded-sm`),
  curvy minor (buttons `rounded-lg`, badges/tabs/pills `rounded-full`).
  Sidebar has a depth gradient (`bg-depth-gradient`); active nav = left border
  + primary tint (well-log track marker look).

## Navigation
- Real routes via react-router: `/`, `/deck-builder`, `/deck-editor`, `/simulator`,
  `/results`, `/learn`, `/chat`, `/linter`, `/settings`. Sidebar and Header both
  render `NavLink`s (they duplicate the navItems array - keep in sync).
- Deep links work because the backend serves index.html for extension-less 404s
  (SPAStaticFiles in opm_ai/api/server.py). Paths WITH extensions still 404 so a
  broken asset hash fails loudly.

## Key Files
- `src/stores/useAppStore.ts` - Zustand slices: settings, chat, deck, lint,
  simulation, UI (+ theme). **All object-returning selectors MUST wrap in
  `useShallow`** (zustand v5 + fresh object literal = infinite re-render,
  React error #185, blank page). Persistence: chat persists `sessionId` AND
  `messages` (server keeps history keyed by sessionId; an empty UI after reload
  silently diverges); simulation persists `jobHistory`, `lastResults`,
  `currentJob`; settings persists only `llmProvider` (keys NEVER in localStorage);
  UI persists only `theme`. `useResolvedTheme()` lives here too.
- `src/api/client.ts` - REST + WebSocket client. `connectChat` invariants:
  intentional `close()` sets closedByUser and cancels the reconnect timer (no
  orphan sockets); `send()` while not OPEN queues in `pendingSend`, flushed on
  next open (never silently dropped); reconnect max 5 attempts, counter resets
  on open. The `tool_call` WS event arrives FLAT from the backend
  (`{tool_name, arguments, tool_call_id}`, chat.py) and is converted here into
  the nested OpenAI-style `ToolCall` the components render. fetchJson reads
  error bodies once as text (a Response body cannot be read twice).
- `src/types.ts` - `WSServerMessage` mirrors the actual wire shape (flat
  tool_call). If the backend protocol changes, change it here AND in client.ts.
- `src/components/SimulationRunner.tsx` - deck path input + **Browse button**
  (hidden file input, .DATA only, uploads via POST /api/decks, fills the path);
  "Use Last Built Deck" saves current deck text the same way. On mount it
  reconciles a persisted running job against GET /api/run/{id} (backend job
  store is in-memory; a server restart orphans jobs -> marked failed).
- `src/components/ResultsViewer.tsx` - KPI cards, Plotly (theme-aware),
  3D View tab (placeholder - see FORWARD_PLAN), 3D Snapshots tab (real PNGs).
- `src/components/ChatPanel.tsx` - connects once per sessionId (connection in
  a ref, callbacks read latest state via useChatStore.getState()); provider
  select is store-controlled (revert on API failure = revert the store, no DOM
  mutation).
- `src/components/DeckBuilder.tsx` / `DeckEditor.tsx` / `LinterPanel.tsx` -
  Monaco with theme switching; lint = save text via POST /api/decks then POST
  /api/lint with the returned path.
- `src/components/SettingsPanel.tsx` - GET/POST /api/settings; keys live in
  component state only, POSTed on save, cleared after.
- Deleted 2026-07-22: `src/theme.ts` (dead duplicate palette), `src/App.css`.

## KPI Card Keys (must match `opm_ai/postprocess/kpi.py::extract_kpis` output exactly)
| Key | Label | Unit | Format |
|-----|-------|------|--------|
| `days` | Simulation Days | days | `v.toFixed(0)` |
| `field_oil_recovery` | Cumulative Oil | STB | `v.toLocaleString()` |
| `field_water_recovery` | Cumulative Water | STB | `v.toLocaleString()` |
| `field_gas_recovery` | Cumulative Gas | MSCF | `v.toLocaleString()` |
| `max_watercut` | Max Water Cut | % | `(v*100).toFixed(1)` |
| `final_gor` | Final GOR | MSCF/STB | `v.toFixed(2)` |
| `producer_count` | Producers | - | `v.toFixed(0)` |
| `plateau_duration_days` | Plateau Duration | days | `v.toFixed(0)` |

**Units**: FIELD units (STB, MSCF, psia). **Null handling**: plain ASCII `-`.

## Dev / Prod Serving
- Vite dev server (5173) proxies `/api` -> `http://localhost:8000` (vite.config.ts).
- Prod: FastAPI serves `frontend/dist` at `/` via SPAStaticFiles; dist is
  gitignored, Docker builds it in-stage.

## Testing
- Playwright (python sync_api, headless chromium 1400x900) against
  http://localhost:8000. Set Monaco content via
  `window.monaco.editor.getModels()[0].setValue(...)`. Watch `page.on("pageerror")`;
  a blank body usually means the useShallow rule was violated.
- Curated screenshots for the README live in `docs/screenshots/` (repo root).

## Future Work (see FORWARD_PLAN.md "Planned capabilities" for details)
- Real 3D View tab content (currently placeholder; snapshots tab already works)
- Render backend `lint_summary` (LLM plain-English lint) in Linter/DeckEditor
- Correlation selection dropdown in the fluid card
- Code-split Plotly/Monaco (5.2MB single bundle is accepted debt)
- Monaco inline lint squiggles; mobile polish
