# Part 6 - Conversational AI Layer (module: opm_ai.api + frontend/)

> FastAPI backend exposing build/lint/run/results/chat endpoints and a React+Vite+TypeScript SPA consuming them.

## 1. Role in the AIM

This part delivers the chat-driven educational workbench: a user types plain English, the LLM router decides which module function to call (build_deck, lint_deck, run_simulation, get_kpis, open_resinsight_plot), the backend executes it, and the frontend streams the response and renders decks, logs, KPIs, Plotly charts, and ResInsight snapshots side-by-side. It is the single user-facing interface that makes OPM Flow accessible without deck syntax knowledge.

## 2. Position in build order

| Phase | Stage | Depends on | Depended on by |
|-------|-------|------------|----------------|
| 2 (v1.1) | Stage 5 (FastAPI backend) | Parts 1-4 (runner, linter, builder, postprocess) + `pyproject.toml` adds `fastapi`, `uvicorn[standard]` | Stage 6 (frontend), Stage 7 (explainer) |
| 2 (v1.1) | Stage 6 (React frontend) | Stage 5 (running `/api/*` endpoints) | Phase 3 (explainer/RAG UI) |
| 2 (v1.1) | Part 8 (deployment skeleton) | Stage 5-6 (Dockerfile, compose, README quick-start) | - |

Key point: Stage 5 must be runnable (`uvicorn opm_ai.api.server:create_app --factory`) before Stage 6 starts; the frontend dev server proxies `/api` to it via Vite.

## 3. Hard API contract (exact signatures this part must satisfy)

**Backend - `api/server.py`**

```python
def create_app() -> FastAPI:
    """Factory returning a FastAPI instance with:
    - CORS allow_origins = ["http://localhost:5173"] (Vite default)
    - Optional static mount of frontend/dist at "/" when built artefacts exist
    - Routers included: build, lint, run, results, chat
    """
```

**Backend - `api/schemas.py` (Pydantic DTOs)**

```python
# Build
class BuildRequest(BaseModel):
    description: str
    output_path: str | None = None

class BuildResponse(BaseModel):
    deck: str
    lint: LintResult

# Lint
class LintRequest(BaseModel):
    deck_path: str

class LintResult(BaseModel):
    deck_path: str
    errors: list[str]
    passed: bool

# Run (async job)
class RunRequest(BaseModel):
    deck_path: str
    timeout: int = 120

class JobStatus(BaseModel):
    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    result: SimulationResult | None = None
    error: str | None = None

# Results
class KPIsResponse(BaseModel):
    kpis: dict
    plots: dict[str, str]  # plot_name -> Plotly JSON (fig.to_json())

# Chat (streaming)
class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    session_id: str
```

**Backend - `api/routes/` thin adapters (no business logic)**

| Route | Method | Path | Delegates to | Returns |
|-------|--------|------|--------------|---------|
| build | POST | `/api/build` | `builder.builder.build_deck` | `BuildResponse` |
| lint | POST | `/api/lint` | `linter.linter.lint_deck` | `LintResult` |
| run | POST | `/api/run` | `runner.runner.run_simulation` (background) | `JobStatus` (job_id) |
| run status | GET | `/api/run/{job_id}` | in-memory job store | `JobStatus` |
| results | GET | `/api/results/{job_id}` | `postprocess.summary.read_summary` + `kpi.extract_kpis` + `plots.plot_production/pressure` | `KPIsResponse` |
| chat | WS | `/api/chat` | `llm.client.LLMClient` + tool router | streaming tokens + tool calls |
| files (browse) | GET | `/api/files?path=` | `validate_path` allowlist + dir scan | `DeckListResponse` (real server paths, INCLUDEs resolve) |
| upload_deck | POST | `/api/upload_deck` | `tempfile.mkdtemp` + multipart write | `UploadResponse` (deck_path for /api/run) |

The Browse vs Upload split exists because each tool is the right answer for a different user:

- **Browse** (`/api/files`): the deck is already on the server. Pick a
  path; the deck stays among its own siblings; relative INCLUDE paths
  resolve exactly as they do when Flow is run by hand.
- **Upload** (`/api/upload_deck`): the deck is on the user's laptop.
  The user picks the `.DATA` plus an optional `include/` folder in a
  single multipart POST; the backend writes them to a fresh
  `tempfile.mkdtemp(prefix="opm_ai_upload_")` under the system temp
  dir (inside `get_allowed_roots()`), returns the `.DATA`'s
  server-side path. Both flows converge on the same wire contract:
  `/api/run` only cares about a real path on the server.

The previous Browse button uploaded the `.DATA` bytes alone via a
plain `<input type="file">`, which orphaned any `include/` tree on
the user's laptop — Flow aborted on the first missing `.grdecl`.
That bug is what motivated the Browse → server-side path picker in
the first place; Upload is the symmetric tool for the laptop case.

**Frontend - `src/api/client.ts` (typed wrappers)**

```typescript
export const api = {
  build: (req: BuildRequest) => fetchJson<BuildResponse>("/api/build", req),
  lint: (req: LintResult) => fetchJson<LintResult>("/api/lint", req),
  run: (req: RunRequest) => fetchJson<JobStatus>("/api/run", req),
  runStatus: (jobId: string) => fetchJson<JobStatus>(`/api/run/${jobId}`),
  results: (jobId: string) => fetchJson<KPIsResponse>(`/api/results/${jobId}`),
  chat: (messages: ChatMessage[], sessionId: string) =>
    websocket("/api/chat", { messages, session_id: sessionId }),
  listDecks: (path?: string) => fetchJson<DeckListResponse>(
    path ? `/files?path=${encodeURIComponent(path)}` : "/files"
  ),
  // form is a multipart/form-data FormData; the helper does NOT
  // set Content-Type (browser sets it with the correct boundary=).
  uploadDeck: (form: FormData) => fetchMultipart<UploadResponse>("/upload_deck", form),
};
```

**Test gate (to be added):** `tests/integration/test_api.py` using `fastapi.testclient.TestClient` covering:
- `POST /api/build` -> deck contains RUNSPEC/GRID/PROPS/SOLUTION/SCHEDULE, lint.passed=true
- `POST /api/lint` on SPE1 -> `LintResult(passed=True, errors=[])`
- `POST /api/run` -> returns job_id, `GET /api/run/{id}` eventually `status="completed"`
- `GET /api/results/{id}` -> `kpis.days > 0`, `plots.production` is valid Plotly JSON
- `WS /api/chat` -> streams tokens, emits tool_call for `build_deck` when user asks "build a depletion deck"
- `POST /api/upload_deck` (deck-only) -> 200, deck_path returned, file exists, passes `validate_deck_path` (regression guard for the `/api/run` contract).
- `POST /api/upload_deck` (deck + include/) -> 200, nested layout preserved, leading `include/` prefix stripped from `webkitRelativePath`.
- `POST /api/upload_deck` -> 400 on missing deck / non-`.DATA` filename / empty file / `..` traversal / absolute path / duplicate include; 415 on non-multipart.

## 4. Key design decisions

| # | Decision | Rationale | Alternatives considered | Consequences |
|---|----------|-----------|------------------------|--------------|
| 1 | **FastAPI over Flask** | Native async, pydantic-native DTOs (we already depend on pydantic), first-class `StreamingResponse` and WebSocket support for LLM chat. | Flask + Quart (async Flask) - adds dependency, no pydantic integration. | Slightly larger dep tree (`starlette`, `uvicorn`), but cleaner async code. |
| 2 | **Vite + React + TS over Next.js / CRA** | No SSR needed (pure SPA), Vite dev server is faster, TypeScript first-class, smaller bundle. | Next.js (overkill, adds server runtime), Create React Abandoned (unmaintained). | Must configure Vite proxy for `/api`; no built-in API routes (by design - we own the backend). |
| 3 | **Agentic router = OpenAI-style function calling** | Each module function (`build_deck`, `lint_deck`, `run_simulation`, `get_kpis`, `open_resinsight_plot`) exposed as a tool with JSON schema. LLM sees user message + tool list + session state, picks tool. Proven pattern (OpenAI Assistants, LangGraph). | LangChain agent executor - adds heavy dep, deferred to Phase 3. Manual `if/elif` routing - brittle, doesn't scale to multi-turn. | Requires LLM with function-calling (Groq Llama-3.3-70B, NVIDIA NIM). Offline fallback: router returns canned "API key required" message. |
| 4 | **System prompt as authored domain artifact (500-800 words)** | Highest-leverage human artifact per GUIDE 3 Part 6. Encodes reservoir-engineering judgement: what "physically valid" means, reasonable GOR ranges, WBHP limits, depletion vs waterflood templates, when to ask clarifying questions. Not generated - written once, version-controlled. | Embedding in code as string constant - hard to review. External file loaded at startup - chosen. | Must be loaded at `LLMClient` init; hot-reload not required. |
| 5 | **Streaming: WebSocket for chat, background task + polling for `/api/run`** | Chat needs token-by-token streaming (WebSocket). Simulation runs 10-120s -> blocking request would timeout proxies; background task + `GET /api/run/{id}` polling (2s interval) is standard pattern. | SSE for chat - works but WebSocket simpler for bidirectional tool calls. Long-polling for run - more complex server state. | Frontend `ChatPanel` uses WebSocket; `SimulationRunner` polls status endpoint. |
| 6 | **In-memory session state (dict keyed by session_id)** | Docker handles persistence (container restart = session reset acceptable for v1). No Redis/DB yet. | SQLite / Redis - adds infra, deferred. | Session lost on backend restart; acceptable for educational single-user flow. |
| 7 | **Plotly serialization via `fig.to_json()`** | Plotly figures are JSON-serialisable; frontend `Plotly.react()` consumes directly. No custom schema needed. | Custom plot spec - reinvents wheel. | Frontend `ResultsViewer` calls `Plotly.newPlot(div, JSON.parse(plotJson))`. |
| 8 | **pyproject.toml / README drift fix** | BUILD_GUIDE section 2 mandates: add `fastapi`, `uvicorn[standard]`; drop `streamlit`; update quick-start to `uvicorn opm_ai.api.server:create_app --factory` + `cd frontend && npm run dev`. Cross-ref 08-deployment.md. | Leave as-is - confusing for new users. | Breaking change for anyone following old README; must be in Phase 2 commit. |

## 5. Toolchain grounding (exact paths, versions, APIs)

| Component | Path / Version | Source | Status |
|-----------|----------------|--------|--------|
| FastAPI | `fastapi>=0.110` (pyproject) | BUILD_GUIDE section 2 | **VERIFIED** (not yet in pyproject.toml - must add) |
| Uvicorn | `uvicorn[standard]>=0.29` (pyproject) | BUILD_GUIDE section 2 | **VERIFIED** (not yet in pyproject.toml - must add) |
| React | `react@18`, `react-dom@18` (frontend/package.json) | BUILD_GUIDE section 3 | **VERIFIED** (not yet created) |
| Vite | `vite@5`, `@vitejs/plugin-react` (frontend/package.json) | BUILD_GUIDE section 3 | **VERIFIED** (not yet created) |
| TypeScript | `typescript@5` (frontend/package.json) | BUILD_GUIDE section 3 | **VERIFIED** |
| Plotly.js | `plotly.js-dist@2` (frontend/package.json) | BUILD_GUIDE section 4 (plots) | **VERIFIED** |
| Groq SDK | `groq>=0.9` (pyproject) | BUILD_GUIDE section 2 | **VERIFIED** (in pyproject.toml) |
| OpenAI SDK | `openai>=1.0` (pyproject) | BUILD_GUIDE section 2 | **VERIFIED** (in pyproject.toml) |
| OPM Flow | `/usr/bin/flow` v2026.04 | OPM.md, GUIDE 4 | **VERIFIED** |
| ResInsight | `/usr/bin/ResInsight`, gRPC :50051 | OPM.md, GUIDE 4 | **VERIFIED** |
| rips client | `pip install rips` | GUIDE 4 | **VERIFIED** |
| resfo (deck output) | `resfo>=5.0` (pyproject) | BUILD_GUIDE section 2 | **VERIFIED** |
| **UNVERIFIED** | WebSocket vs SSE performance under Docker | - | Load-test in Stage 6 |
| **UNVERIFIED** | Exact Plotly JSON schema compatibility (Plotly.py -> Plotly.js) | - | Test in `test_api.py` |

## 6. Implementation approach (ordered steps)

### Stage 5 - FastAPI backend

1. **Add deps**: Edit `pyproject.toml` -> add `fastapi`, `uvicorn[standard]`; remove `streamlit`.
2. **Create package skeleton**:
   ```
   opm_ai/api/__init__.py
   opm_ai/api/server.py
   opm_ai/api/schemas.py
   opm_ai/api/routes/__init__.py
   opm_ai/api/routes/build.py
   opm_ai/api/routes/lint.py
   opm_ai/api/routes/run.py
   opm_ai/api/routes/results.py
   opm_ai/api/routes/chat.py
   ```
3. **`schemas.py`**: Define all DTOs per section 3 (Pydantic v2, `ConfigDict(from_attributes=True)`).
4. **`server.py`**: `create_app()` factory; CORS `allow_origins=["http://localhost:5173"]`; optional `app.mount("/", StaticFiles(directory="frontend/dist", html=True))` guarded by `Path("frontend/dist").exists()`; include routers with prefix `/api`.
5. **`routes/build.py`**: `POST /build` -> validate `BuildRequest` -> `deck, lint = build_deck(req.description, Path(req.output_path) if req.output_path else None)` -> return `BuildResponse(deck=deck, lint=lint)`.
6. **`routes/lint.py`**: `POST /lint` -> `lint_deck(Path(req.deck_path))` -> return `LintResult`.
7. **`routes/run.py`**: 
   - `POST /run` -> generate `job_id = uuid4()`, store `JobStatus(status="pending")` in `app.state.jobs: dict[str, JobStatus]`, launch `asyncio.create_task(run_job(job_id, req))` -> return `JobStatus(job_id=job_id, status="pending")`.
   - Background task: update status to "running", call `run_simulation(SimulationJob(...))`, on success store `SimulationResult`, status="completed"; on exception store `error`, status="failed".
   - `GET /run/{job_id}` -> return stored `JobStatus`.
8. **`routes/results.py`**: `GET /results/{job_id}` -> load `SimulationResult`, call `read_summary(output_dir)`, `extract_kpis(df)`, `plot_production(df).to_json()`, `plot_pressure(df).to_json()` -> return `KPIsResponse`.
9. **`routes/chat.py`**: 
   - WebSocket endpoint `/chat` accepting `ChatRequest` (JSON first message).
   - Load system prompt from `opm_ai/api/system_prompt.md` (authored document).
   - Maintain per-session message history in `app.state.sessions: dict[str, list[ChatMessage]]`.
   - Loop: call `LLMClient.chat(messages + [system_prompt])` with `tools=[build_deck_tool, lint_deck_tool, run_simulation_tool, get_kpis_tool, open_resinsight_plot_tool]`.
   - If LLM returns `tool_calls`, execute corresponding function, append `tool` message, stream result back.
   - Stream assistant tokens via `websocket.send_text(json.dumps({"type": "token", "content": chunk}))`.
   - Tool definitions: JSON schema derived from `schemas.py` DTOs (use `model_json_schema()`).
10. **Write `tests/integration/test_api.py`** using `TestClient` covering all happy paths.
11. **Run**: `uvicorn opm_ai.api.server:create_app --factory --reload` -> verify `/docs` loads.

### Stage 6 - React frontend

1. **Scaffold**: `cd frontend && npm create vite@latest . -- --template react-ts`.
2. **Configure**:
   - `vite.config.ts`: `server: { proxy: { "/api": "http://localhost:8000" } }`.
   - `tsconfig.json`: strict mode, path aliases `@/*: src/*`.
   - Install deps: `react`, `react-dom`, `plotly.js-dist`, `zustand` (lightweight state), `monaco-editor` (DeckBuilder syntax highlight).
3. **`src/api/client.ts`**: Typed fetch + WebSocket wrapper per section 3.
4. **Theme**: `src/theme.ts` - Dark Void (bg `#0d0d0d`, fg `#e0e0e0`, accent `#00ff88`, mono `JetBrains Mono`).
5. **`src/App.tsx`**: Sidebar (Chat / Deck Builder / Simulation Runner / Results / Settings) + outlet.
6. **Components**:
   - `ChatPanel.tsx`: WebSocket connection, message list, streaming token render, tool-call badges.
   - `DeckBuilder.tsx`: Textarea + Monaco editor (read-only rendered deck), "Build" button -> `api.build()`.
   - `SimulationRunner.tsx`: File picker or generated deck path, "Run" -> polls `api.runStatus()`.
   - `ResultsViewer.tsx`: KPI cards + `Plotly.newPlot` for production/pressure plots, ResInsight snapshot `<img>` placeholders.
   - `LinterPanel.tsx`: Paste deck -> `api.lint()` -> error list with line numbers.
   - `SettingsPanel.tsx`: API key inputs (Groq, NVIDIA NIM base_url), provider select, persisted to `localStorage` and sent to backend via header `X-API-Keys`.
7. **Build**: `npm run build` -> outputs to `frontend/dist` (served by FastAPI static mount in prod).
8. **Dev flow**: Terminal 1: `uvicorn ...`; Terminal 2: `cd frontend && npm run dev` -> open `http://localhost:5173`.

## 7. Risks and open questions

| Risk | Mitigation / Decision needed |
|------|------------------------------|
| **WebSocket proxy in Docker** | Vite proxy works in dev; production needs nginx or FastAPI `WebSocketRoute` behind same origin. Decide in 08-deployment.md. |
| **LLM function-calling reliability** | Groq Llama-3.3-70B supports tools; NVIDIA NIM (OpenAI-compatible) must be verified. Fallback: keyword-based router for offline mode. |
| **Session state loss on backend restart** | Acceptable for v1 (single-user educational). Document in README. |
| **Plotly version mismatch (Python 5.x vs JS 2.x)** | Pin both in lockfiles; test `fig.to_json()` round-trip in `test_api.py`. |
| **Long-running simulation blocks event loop** | `run_simulation` is sync subprocess; run in `loop.run_in_executor(None, run_simulation, job)` to avoid blocking FastAPI. |
| **ResInsight bridge not yet implemented (Part 5)** | `open_resinsight_plot` tool returns placeholder `{status: "not_implemented"}`; wire real `rips` call in Phase 2 tail. |
| **CORS / credentials in production** | Dev: `allow_origins=["http://localhost:5173"]`. Prod: `allow_origins=[settings.FRONTEND_ORIGIN]`, `allow_credentials=True`. |
| **API key management** | Frontend stores keys in `localStorage`; sends via header. Backend validates per-request. No server-side persistence in v1. |
| **Upload size & filesystem pressure** | `/api/upload_deck` allows up to 256 MB / part and 5000 parts. A user uploading a 73 MB include/ tree plus the deck briefly holds ~150 MB on disk under `/tmp`. Acceptable on a workstation; production should mount `/tmp` with sufficient inode/size headroom. |
| **Upload dir cleanup** | There is no reaper for partial upload dirs (interrupted mid-write). A periodic task keyed on `opm_ai_upload_*` mtime should clean anything older than 24 h. Out of scope for v1. |

## 8. Verification and done-criteria

| Criterion | How to verify |
|-----------|---------------|
| FastAPI factory serves | `uvicorn opm_ai.api.server:create_app --factory` starts, `curl localhost:8000/docs` returns OpenAPI JSON |
| `POST /api/build` happy path | `pytest tests/integration/test_api.py::test_build_deck -v` passes |
| `POST /api/lint` on SPE1 | `pytest tests/integration/test_api.py::test_lint_spe1 -v` passes (`passed=True, errors=[]`) |
| `POST /api/run` + poll | `pytest tests/integration/test_api.py::test_run_simulation -v` passes (job completes, `success=True`) |
| `GET /api/results/{id}` | `pytest tests/integration/test_api.py::test_results_kpis_plots -v` passes (`kpis.days>0`, valid Plotly JSON) |
| `WS /api/chat` streams | `pytest tests/integration/test_api.py::test_chat_stream -v` passes (receives token frames, tool_call for build_deck) |
| Frontend builds | `cd frontend && npm run build` exits 0, `dist/index.html` exists |
| Dev loop works | `uvicorn` + `npm run dev` -> open `localhost:5173` -> Chat panel sends "build a 10x10x3 depletion deck" -> deck appears in DeckBuilder, lint passes |
| pyproject.toml clean | `streamlit` removed; `fastapi`, `uvicorn[standard]` present; `pip install -e .` succeeds |
| README quick-start updated | Cross-ref 08-deployment.md; commands are `uvicorn ...` + `npm run dev` |

## 9. Visual Design Reference

See `docs/conversations/UI_DESIGN_SPEC.md` for the complete extracted design system from `docs/Reference_UI.png` (4-panel reference showing Home/Dashboard, Deck Editor, Deck Builder workflow, and ResInsight Results views). Key decisions:

- **Palette:** Dark blue base (#0A1628), cyan accents (#00D9FF), not the warm/earthy design_sense defaults - the reference UI is authoritative for this technical domain.
- **Components:** Monaco editor for deck syntax highlighting, collapsible section tree (RUNSPEC/GRID/PROPS/SOLUTION/SCHEDULE), Plotly charts with dark theme, Three.js or deck.gl for 3D geomodel grid visualization.
- **Layout:** Horizontal top nav (7 functions: Home, Deck Builder, Data Linter, Reservoir Engineering, Simulator, ResInsight Results, AI Explainer), vertical left sidebar (section tree or icon nav), main content area, optional right sidebar for diagnostics/filters/validation summary.
- **4 Main Views:** 
  - `/` (home/dashboard with capability highlights)
  - `/deck-builder` (guided workflow forms with PVT/SCAL charts and data tables)
  - `/deck-editor` (Monaco syntax editor with real-time validation, section tree navigation, template selection)
  - `/results` (3D property visualization + time-series plots + cross-plots + flow diagnostics)
- **Status Indicators:** Progress bars (cyan fill), badges (cyan "OG Banges" style pills for operational status), green checkmarks for validation passed, yellow warnings for attention needed.
- **Interactive Elements:** Cyan primary buttons, dark dropdowns, sliders with cyan track/thumb, toggles cyan when active.

## 10. Future extensions

- **Auth / multi-user**: Add FastAPI `Depends(get_current_user)`, per-user job store (Redis/SQLite), WebSocket auth handshake.
- **Persistent sessions**: Migrate `app.state.sessions` to Redis with TTL; survive backend restarts.
- **Server-sent events (SSE) fallback**: For environments blocking WebSocket (corporate proxies).
- **ResInsight live embed**: `rips` can export interactive HTML (WebGL); serve via `/api/resinsight/{job_id}` iframe.
- **Streaming run logs**: WebSocket `/api/run/{job_id}/logs` tailing `CASE.PRT` in real time.
- **RAG-enhanced chat (Phase 3)**: Inject retrieved textbook chunks into system prompt per user question.

## Upload endpoint caveats (not bugs, just operational notes)

- **Starlette multipart limits**: `max_part_size` is overridden to 256 MB and `max_files` to 5000 on the route, via `await request.form(max_part_size=..., max_files=...)`. Starlette defaults (1 MB / 1000) would reject any non-trivial deck — some `.grdecl` include files in `model2` are 30-50 MB and the include/ tree is 73 MB across 1000+ files.
- **Upload dir lifecycle**: `/api/upload_deck` writes to a fresh `tempfile.mkdtemp(prefix="opm_ai_upload_")` under the system temp dir. There is no reaper; partial uploads on interrupt are left behind. The next upload picks a fresh `mkdtemp`. Production should add a periodic cleanup task keyed on `opm_ai_upload_*`.
- **webkitdirectory is Chromium-only**: The `<input type="file" webkitdirectory directory multiple>` attribute set that the `DeckUploader` uses for the include/ folder picker is non-standard (Chromium-only). Firefox/Safari users get a plain multi-file picker that doesn't preserve the include/ layout; the deck upload alone still works on any browser. A polyfill could come later if needed.
- **Returned `deck_path` passes `validate_deck_path`**: This is the contract that lets the upload endpoint slot into the existing `/api/run` flow unchanged. Pinned by `test_upload_returned_path_passes_validate` in `tests/integration/test_api_upload_deck.py`.

---
*Cross-refs: 00-overview-and-architecture.md (stack), 01-runner.md (run_simulation contract), 02-linter.md (lint_deck contract), 03-builder.md (build_deck contract), 05-postprocess.md (read_summary/extract_kpis/plots), 08-deployment.md (Dockerfile, compose, README quick-start).*