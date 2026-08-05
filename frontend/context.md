# Frontend Context

Last updated: 2026-08-04 (audit pass; substantive module content unchanged
since 2026-08-03 — server-side deck picker, snapshots tab removed,
vendor chunk split, dead deps dropped remain the shipped state).

## Stack
- **Framework**: React 18 + Vite 5 + TypeScript 5, react-router-dom v6 (BrowserRouter)
- **Styling**: Tailwind CSS 3.4 over CSS custom properties (see Theme System below)
- **State**: Zustand v5 with persist middleware (`src/stores/useAppStore.ts`)
- **API Client**: Typed client in `src/api/client.ts` matching `opm_ai/api/schemas.py` DTOs
- **Editor**: Monaco (@monaco-editor/react), custom OPM language, `opm-dark`/`opm-light` themes
- **Charts**: Plotly via plotly.js-dist-min (layout restyled client-side per theme)
- **Build**: `NODE_OPTIONS=--max-old-space-size=3000 npm run build` (sourcemaps OFF;
  on this 3GB host stop uvicorn first or the build gets OOM-killed)
- **Chunks** (`vite.config.ts` manualChunks, 2026-08-03): the bundle was one
  5.8 MB file, so any app-code edit invalidated the whole thing in every
  browser cache. Now four: app ~385 kB, three ~537 kB, plotly ~4.84 MB,
  monaco ~22 kB. Note plotly, not three.js, is the elephant. This is output
  grouping only, not lazy loading; every chunk is still modulepreloaded on
  first paint. Real lazy loading would need React.lazy + Suspense, which
  changes mount timing and was deliberately left alone.
- **Tests**: `npm test` runs `src/components/viewer3d/meshFormat.test.ts`, a
  plain assert script bundled with the esbuild that ships inside vite. There is
  no vitest/jest here on purpose: the script already covers the binary parsers
  and passes 19 checks, and Node on this host is 18.x.

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
  (opens `DeckPicker`, which lists decks server-side via GET /api/files and
  hands back a path). It deliberately does NOT upload: a browser file input
  gives one file's bytes with no real path and no siblings, so a deck with
  INCLUDE keywords loses its include/ folder and Flow cannot resolve them.
  Flow resolves INCLUDE against the deck's own directory, so the deck has to
  stay where it lives. "Use Last Built Deck" still saves deck text via POST
  /api/decks, which is fine because generated text has no includes. On mount
  it reconciles a persisted running job against GET /api/run/{id} (backend job
  store is in-memory; a server restart orphans jobs -> marked failed).
- `src/components/DeckPicker.tsx` - modal browser over GET /api/files: root
  chips, `..` navigation, INCLUDE badges, sizes, Escape to close.
- `src/components/ResultsViewer.tsx` - KPI cards, Plotly (theme-aware) and the
  3D View tab (see 3D Viewer below). There is no snapshots tab; it was removed
  in bfa0acd. It shelled out to ResInsight batch mode, which on a host with a
  live X display reports success while writing a 329x127 crop of the ResInsight
  window with no grid in it, and cannot run headless at all (the packaged
  2026.06 build has no gRPC and segfaults under QT_QPA_PLATFORM=offscreen).
  The backend route, the api client method and the chat tool still exist and
  are still tested; only the UI entry point is gone.
- `src/components/ChatPanel.tsx` - connects once per sessionId (connection in
  a ref, callbacks read latest state via useChatStore.getState()); provider
  select is store-controlled (revert on API failure = revert the store, no DOM
  mutation).
- `src/components/DeckBuilder.tsx` / `DeckEditor.tsx` / `LinterPanel.tsx` -
  Monaco with theme switching; lint = save text via POST /api/decks then POST
  /api/lint with the returned path.
- `src/components/opmCompletions.ts` (Stage 3.4, 2026-08-04) - Monaco
  keyword completion provider extracted as a pure module so it can be
  unit-tested without React/Monaco. Trigger chars A-Z + 0-9 + `_`.
  `sectionLabel(entry)` rules: "SCHEDULE · 18 args" > "601 decks observed"
  > "Keyword". Falls back to bundled OPM_KEYWORDS list when /api/keywords
  unreachable.
- `src/components/opmCompletions.test.ts` (Stage 3.4) - 9 self-check tests
  via esbuild/node pattern; bundled into `node_modules/.cache/oc.cjs` by
  the `test` script.
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
- The build needs ~3 GB of Node heap since `three` joined the bundle:
  `NODE_OPTIONS=--max-old-space-size=3000 npm run build`. It OOM-kills during
  minify on a 3 GB box with other processes resident; `--minify false` builds
  in less memory if it comes to that.

## Testing
- Playwright (python sync_api, headless chromium 1400x900) against
  http://localhost:8000. Set Monaco content via
  `window.monaco.editor.getModels()[0].setValue(...)`. Watch `page.on("pageerror")`;
  a blank body usually means the useShallow rule was violated.
- Curated screenshots for the README live in `docs/screenshots/` (repo root).

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
| `Grid3DViewer.tsx` | Default export, props `{ jobId, compact? }`. Owns all fetching and panel state, drives the engine. `compact` drops the control panel for the Home hero; everything else stays live. |
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

Mounted in two places, both requiring a **completed** job (the grid endpoints
read the `.EGRID` that OPM Flow writes, so a `.DATA` deck has no geometry to
show until it has run):

- `ResultsViewer.tsx` "3D View" tab, full panel, mounted only while that tab is
  active so the WebGL context and its fetches go away on tab switch.
- `Home.tsx` hero, `compact`, showing the latest completed run from
  `jobHistory` (newest-first; the active job wins while it is still running).
  Fixed height, not `aspect-video`: the viewer sizes from its parent, and
  `zoomAll` frames the model's bounding SPHERE against the vertical FOV, so a
  wide flat grid like Norne reads small in a short letterbox.
  `jobHistory` is persisted to localStorage while the job store is in-memory,
  so a stale id after a backend restart falls through to the viewer's own
  "3D grid unavailable" panel.

## Future Work
- Render backend `lint_summary` (LLM plain-English lint) in Linter/DeckEditor
- Correlation selection dropdown in the fluid card
- Code-split Plotly/Monaco (5.2MB single bundle is accepted debt)
- Monaco inline lint squiggles; mobile polish
- **3D Viewer**: intersections/section planes, contour maps, streamlines and
  multi-view linking are the remaining ResInsight 3D features not implemented.
