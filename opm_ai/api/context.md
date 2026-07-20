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
| `routes/results.py` | GET `/api/results/{job_id}` - KPIs + Plotly JSON plots; `/snapshots` - ResInsight 3D PNG export (render or reuse cache); `/snapshots/{file}` - serve one PNG |
| `routes/chat.py` | WebSocket `/api/chat` + HTTP fallback - LLM chat with tool calling |
| `routes/explainer.py` | POST `/api/explain`, `/api/quiz`, `/api/learning-report` - Educational explainer API |

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