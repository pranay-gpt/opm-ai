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
| `server.py` | FastAPI app factory (`create_app`), lifespan, CORS, static mount, router inclusion |
| `schemas.py` | Pydantic DTOs for requests/responses and OpenAI tool schemas |
| `job_store.py` | In-memory job store (module-global dict) for async simulation runs |
| `routes/build.py` | POST `/api/build` - build deck from natural language |
| `routes/lint.py` | POST `/api/lint` - lint a deck file |
| `routes/run.py` | POST `/api/run` (start job), GET `/api/run/{job_id}` (poll status) |
| `routes/results.py` | GET `/api/results/{job_id}` - KPIs + Plotly JSON plots |
| `routes/chat.py` | WebSocket `/api/chat` + HTTP fallback - LLM chat with tool calling |

## Future Plan

### 1. Path Validation & Sandboxing for `deck_path` Inputs
- Current: routes accept arbitrary `deck_path` strings and pass to `Path()`
- Need: Validate paths are within allowed directories (e.g., `/app/decks`, `/app/results`)
- Implement path traversal protection (`Path.resolve().is_relative_to(allowed_root)`)

### 2. Session Eviction
- Current: `app.state.sessions` dict grows unbounded (WebSocket chat history)
- Need: TTL-based eviction or max-sessions limit with LRU cleanup
- Consider: Redis-backed sessions for multi-worker deployments

### 3. Redis Job Store for Multi-Worker
- Current: In-memory `job_store._jobs` dict (single process only)
- Need: Replace with Redis-backed store (`redis-py` + JSON serialization)
- Maintain same `job_store` API for drop-in replacement
- Enables horizontal scaling with multiple uvicorn workers

### 4. Structured Logging & Observability
- Add structured logging (structlog) with request IDs
- Prometheus metrics endpoint (`/metrics`)
- Distributed tracing headers propagation

### 5. Authentication & Authorization
- API key authentication for `/api/*` routes
- Role-based access (read-only vs. write operations)
- Session authentication for WebSocket chat

### 6. Input Validation Hardening
- Pydantic validators for `deck_path` (must exist, must be .DATA file)
- Request size limits
- Rate limiting on expensive endpoints (build, run)