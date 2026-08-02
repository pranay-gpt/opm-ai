# opm_ai/api - FastAPI Backend Module

## Module Purpose
This module provides the FastAPI backend for the OPM AI application, exposing REST and WebSocket endpoints for:
- Building OPM Flow decks from natural language descriptions
- Linting deck files for syntax and best practices
- Running simulations as background jobs
- Retrieving KPIs and plots from completed simulations
- Chat interface with LLM-powered tool calling

## Key Invariants

### 1. Thin Route Adapters
All route handlers in `routes/` are thin adapters that:
- Validate input via Pydantic models (`schemas.py`)
- Delegate business logic to domain modules (`builder`, `linter`, `runner`, `postprocess`)
- Return Pydantic response models
- Do NOT contain business logic

### 2. Job Store is Module-Global (`job_store.py`)
- The job store is a module-level dictionary `_jobs: dict[str, JobStatus]`
- It is NOT stored in `app.state.jobs` (removed in code review fix)
- Routes import `create_job`, `get_job`, `set_job_running`, `set_job_completed`, `set_job_failed` from `job_store`
- This allows multiple workers to share state if a proper Redis backend is added later

### 3. NaN-Sanitized KPIs
- `postprocess.kpi.extract_kpis` calls `_sanitize_kpis` before returning
- Any float NaN or ±inf values are replaced with `None`
- Ensures `json.dumps(kpis, allow_nan=False)` never raises `ValueError`
- Matches spec: `water_breakthrough_day` is `None` when never occurs (not NaN)

### 4. System Prompt Cached at Import
- `routes.chat.SYSTEM_PROMPT` is read once at module import into a module-level constant
- `load_system_prompt()` returns the cached constant
- Avoids disk I/O on every WebSocket message

### 5. Offline LLM Fallback
- `builder.extract.extract_parameters_offline` is the default extraction method
- LLM extraction (`use_llm=True`) is optional and only used when an API key is configured
- `LLMClient.available` property checks for valid API keys before enabling LLM features

## File Map

| File | Purpose |
|------|---------|
| `server.py` | FastAPI app factory (`create_app`), lifespan, CORS, SPA static mount, router inclusion |
| `schemas.py` | Pydantic DTOs for requests/responses and OpenAI tool schemas |
| `job_store.py` | In-memory job store (module-global dict) for async simulation runs |
| `paths.py` | `validate_path()` allowlist (decks/, results/, fixtures/, tempdir) |
| `routes/build.py` | POST `/api/build` - build deck from natural language |
| `routes/decks.py` | POST `/api/decks` - write deck TEXT to a temp .DATA (browser-only decks: built or hand-edited, 2026-07-22) |
| `routes/files.py` | GET `/api/files` - list .DATA decks on the server so a path can be picked without copying |
| `routes/lint.py` | POST `/api/lint` - lint a deck file |
| `routes/run.py` | POST `/api/run` (start job), GET `/api/run/{job_id}` (poll status) |
| `routes/results.py` | GET `/api/results/{job_id}` - KPIs + Plotly JSON plots; `/snapshots` - ResInsight 3D PNG export (render or reuse cache); `/snapshots/{file}` - serve one PNG |
| `routes/grid.py` | GET `/api/results/{job_id}/grid/{info,mesh,property,property/range,wells}` - 3D viewer geometry, properties and wells |
| `routes/chat.py` | WebSocket `/api/chat` + HTTP fallback - LLM chat with tool calling |
| `routes/explainer.py` | POST `/api/explain`, `/api/quiz`, `/api/learning-report` - Educational explainer API |
| `routes/settings.py` | GET/POST `/api/settings` - runtime LLM provider/key overrides (Stage C) |

### SPA Serving (2026-07-22)

- `SPAStaticFiles` (server.py) subclasses Starlette StaticFiles and serves
  index.html for 404s ONLY when the requested path's last segment has no file
  extension. Client routes (/linter, /deck-builder) deep-link; a missing
  /assets/x.js still 404s so broken builds fail loudly. StaticFiles RAISES
  starlette.exceptions.HTTPException on missing files (it does not return a
  404 response) - catch that class, not FastAPI's. Mount is last, so /api
  routes keep their own 404s.

### Deck Save Route (2026-07-22)

- POST `/api/decks` body `{content, filename?}` -> `{deck_path}`. Writes to a
  fresh `tempfile.mkdtemp(prefix="opmai_deck_")` (system tempdir is in the
  paths.py allowlist - if that allowlist changes, this route breaks; a test in
  test_api_decks.py guards the lint-by-saved-path flow). Rejects empty content
  (400), >2MB (413), non-bare or non-.DATA filenames incl. backslashes (400).
  Sweeps opmai_deck_* dirs older than 1h on each save (no janitor thread by
  design; add one if save volume grows). UI callers: LinterPanel, DeckEditor,
  SimulationRunner (Use Last Built Deck). Decks that already live on the server
  go through `/api/files` instead - see Deck Selection below.

### Chat WS Protocol (wire shape the frontend depends on)

- Server -> client events: `{type:"token",content}`,
  `{type:"tool_call",tool_name,arguments,tool_call_id}` (FLAT - not nested
  OpenAI shape; frontend client.ts converts), `{type:"tool_result",
  tool_call_id,result}`, `{type:"error",message}`, `{type:"done"}`.
- Client -> server per turn: `{session_id, messages: full list}`; server
  merges (empty server history takes all, else trailing user message).
- If you change this protocol, update frontend/src/types.ts WSServerMessage
  AND the tool_call construction in frontend/src/api/client.ts.

### 3D Grid Endpoints (`routes/grid.py`, 2026-07-26)

- Registered BEFORE `results.router` in `server.py`. Both hang off
  `/results/{job_id}`; every grid path carries a literal `grid` segment so
  neither can shadow `/results/{job_id}/snapshots/{filename}`, and ordering
  keeps that true if results.py grows a wildcard later.
- Binary payloads: `/grid/mesh` returns `pack_mesh` output (magic `OPMG`),
  `/grid/property` returns magic `OPMP` + a padded JSON header + float32 values.
  Layouts are fixed by `docs/3d-viewer-contract.md`; the TypeScript parser in
  `frontend/src/components/viewer3d/meshFormat.ts` depends on them byte for
  byte, and `tests/unit/test_grid3d.py::unpack_mesh` is an independent reader
  that fails if either side drifts.
- Four bounded LRU caches, module-level behind one `Lock`, in the spirit of
  `job_store`: 4 packed meshes keyed by `(stem, EGRID mtime_ns,
  include_inactive, MESH_FORMAT_VERSION)`, 4 cells blobs, 32 property ranges
  keyed by `(stem, UNRST mtime_ns, INIT mtime_ns, name)`, and 2 parsed
  `EclipseGrid` objects keyed by `(stem, EGRID mtime_ns)`. The mtime in every
  key means a re-run of the same job id invalidates without an explicit purge.
- The grid cache lives inside `_open_grid`, which every endpoint funnels
  through, rather than in each route. `/grid/property` is not itself cacheable
  (a different array per time step) and was re-parsing the case on every
  request: ~0.17 s per step on Norne against ~0.01 s once the parse is shared,
  which is the whole cost of scrubbing and playback. Static properties now
  serve in ~0.00 s; a dynamic step still pays one `read_dynamic` UNRST scan
  (~0.04-0.08 s per keyword, so SOIL pays two for SWAT + SGAS).
  Sharing one `EclipseGrid` across executor threads is safe because every read
  is idempotent: `corners()` memoises but recomputes the same array from
  immutable inputs, so a concurrent double-compute only wastes work.
  `test_grid_cache_is_reused_and_keyed_on_mtime` covers reuse, the mtime key
  and the bound.
- The mesh ETag is `sha256(cache key)`, not a hash of the 6 MB body, because
  the body is a pure function of the key. `If-None-Match` returns 304.
- All parsing goes through `run_in_executor`; resfo reads are CPU-bound
  (Norne: 0.06 s mesh, 0.06 s full 72 MB UNRST scan).
- Error contract: unknown job 404, job not completed 400, no EGRID 404,
  unparseable case 422, unknown property 404, out-of-range step 400.

### Deck Selection: Two Distinct Paths (2026-07-30)

There are two ways a deck reaches `/api/run`, and picking the wrong one is how
INCLUDE support broke:

| Path | Endpoint | Deck lives | INCLUDE works |
|---|---|---|---|
| Browser-only text (built, or edited in Monaco) | POST `/api/decks` | fresh `mkdtemp` | No - nothing to include |
| A deck already on the server | GET `/api/files` then run the returned path | where it already is | Yes |

- `POST /api/decks` writes **one file** into a fresh temp dir. That is correct
  for deck text that only exists in the browser, and wrong for anything with an
  INCLUDE: the `include/*.grdecl` siblings stay on the user's disk and Flow
  aborts with "File '...' included via INCLUDE directive does not exist".
- The old Browse button used that endpoint, reading a `.DATA` through an
  `<input type="file">`. A file input can only ever hand over the bytes of the
  one file chosen - the browser sandbox forbids reading siblings and forbids
  disclosing a real path - so INCLUDE decks could not work that way at all.
  `GET /api/files` replaces it: the user picks a server path, nothing is copied,
  and a 73 MB include tree costs nothing to select.
- **Flow resolves INCLUDE relative to the deck's own directory, not the cwd**
  (verified: `flow` run from `/` with an absolute deck path resolves
  `include/...` correctly). So `runner.py`'s `cwd=deck_path.parent` is not what
  makes this work; leaving the deck in place is. Do not "fix" a future INCLUDE
  bug by changing cwd.
- `/api/files` validates `path` through the same `validate_path` allowlist as
  `/api/run`, so it cannot list outside the configured roots via `..` or a
  symlink, and "up" is only offered while the parent stays inside a root.
- Roots are reordered for presentation (deck dirs before the system temp dir)
  so the picker lands somewhere with decks rather than in the mkdtemp scratch
  area. Membership is unchanged, so this cannot widen what is accepted.
- `OPM_DECKS_ROOT` (optional, unset by default) appends one more allowlisted
  root for a deck library kept outside `tests/fixtures` and `/app/decks`. It
  widens both what `/api/files` lists and what `/api/run` accepts, hence opt-in.
- Output still lands in `deck_path.parent/output_<job>`, so results sit beside
  the case and the 3D viewer's EGRID lookup is unchanged. This requires the
  deck directory to be writable.

### Runtime Settings (Stage C, 2026-07-20)

- POST `/api/settings` body: `{provider: "groq"|"openai"|"nim"|"offline", groq_api_key?, openai_api_key?, nvidia_nim_api_key?}`. Omitted key = untouched; empty string = cleared.
- Mechanism: plain attribute assignment on the module-level `opm_ai.settings.settings` singleton (pydantic-settings v2 allows this; `validate_assignment` is off). IN-MEMORY ONLY: nothing is written to .env or disk, lost on restart by design.
- GET `/api/settings` response: `{provider, active_provider, keys_configured: {groq: bool, openai: bool, nim: bool}}`. NEVER returns key material; POST responds with the same shape.
- `active_provider` is `settings.active_llm_client` resolution: a selected provider without a key resolves to "offline".
- Takes effect without restart because `LLMClient()` reads settings at construction and chat.py constructs one per connection. Do not add an import-time client cache; it would break this invariant.

### Per-Session Chat Lock (Stage C, 2026-07-20)

- `SessionStore.get_session_lock(session_id)` returns a per-session `asyncio.Lock` from a bounded LRU dict (same `max_entries` as the session dict).
- `routes/chat.py` wraps every session read-modify-write in `async with get_session_lock(...)`; the LLM call runs on a history snapshot taken under the lock, outside the lock itself.
- Without the lock, two concurrent connections on one session id lose updates (verified: 25/50 messages lost in the unlocked variant). Test: `tests/integration/test_chat_session_concurrency.py`.

### Explainer Endpoints

| Endpoint | Method | Request Body | Response |
|----------|--------|--------------|----------|
| `/api/explain` | POST | `{topic?: str, kpis?: dict, level: "beginner"\|"intermediate"\|"advanced", context?: dict}` | `{topic, level, text, citations[{source_id,title,url_or_path,snippet}], follow_up_questions[str]}` |
| `/api/quiz` | POST | `{scenario_summary: str, level?, n_questions: int=3 (1-10), topic_focus?: list[str]}` | `{scenario_summary, questions[{question, options[4], correct_index, explanation, level, topic_tags}]}` |
| `/api/learning-report` | POST | `{session_id: str, conversation_history: list[{role,content}], kpis_history?: list[dict]}` | `{session_id, topics_covered[str], explanations_generated, questions_asked, quiz_scores?, key_concepts[str], citations_used, markdown}` |

### Chat Tools (WebSocket /api/chat)

| Tool | Parameters | Returns |
|------|------------|---------|
| `build_deck` | `{description: str, output_path?: str}` | `{deck, lint{deck_path, errors[], passed}}` |
| `lint_deck` | `{deck_path: str}` | `{deck_path, errors[], passed}` |
| `run_simulation` | `{deck_path: str, timeout?: int}` | `{job_id, status: "pending"}` |
| `get_kpis` | `{job_id: str}` | `{kpis, plots{production, pressure}}` |
| `explain_concept` | `{topic: str, level: "beginner"\|"intermediate"\|"advanced"}` | `{topic, level, text (~1500 chars), citations[str], follow_up_questions[str]}` |
| `generate_quiz` | `{scenario_summary: str, n_questions?: int}` | `{scenario_summary, questions_text (Q/A-D/Answer/Explanation format), n_questions}` |

## Future Plan

### 1. Redis Job Store for Multi-Worker
- Current: In-memory `job_store._jobs` dict (single process only)
- Need: Replace with Redis-backed store (`redis-py` + JSON serialization)
- Maintain same `job_store` API for drop-in replacement
- Enables horizontal scaling with multiple uvicorn workers

### 2. Structured Logging & Observability
- Add structured logging (structlog) with request IDs
- Prometheus metrics endpoint (`/metrics`)
- Distributed tracing headers propagation

### 3. Authentication & Authorization
- API key authentication for `/api/*` routes
- Role-based access (read-only vs. write operations)
- Session authentication for WebSocket chat

### 4. Input Validation Hardening (DONE - Stage 3 API hardening)
- Path validation and sandboxing for `deck_path` inputs ✓
- Pydantic validators for `deck_path` (must exist, must be .DATA file)
- Request size limits
- Rate limiting on expensive endpoints (build, run)

### 5. Session Eviction & Bounded Stores (DONE - Stage 3 API hardening)
- Job store: max 200 entries (configurable), LRU eviction of completed jobs ✓
- Session store: max 100 entries (configurable), LRU eviction ✓
- 429 response when all slots occupied by running jobs ✓
- Thread-safe with proper locking ✓