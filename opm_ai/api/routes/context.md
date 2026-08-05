# opm_ai/api/routes/ - FastAPI route handlers

## Purpose
Thin HTTP adapters per resource. Each file is one router with one or
more endpoints. Per project rules (see `opm_ai/api/context.md`):
- Validate input via Pydantic models from `schemas.py`
- Delegate business logic to domain modules (`builder`, `linter`,
  `runner`, `postprocess`, etc.)
- Return Pydantic response models
- No business logic

## Files

| File | Router | Endpoints |
|------|--------|-----------|
| `build.py` | `/api/build` | POST deck build from spec; rock basics extraction |
| `chat.py` | `/api/chat` | WebSocket chat with tool calling |
| `decks.py` | `/api/decks` | CRUD on saved decks; validation |
| `explainer.py` | `/api/explainer` | RAG-backed explanations of deck keywords |
| `files.py` | `/api/files` | Tree browse, deck path resolution |
| `grid.py` | `/api/grid` | 3D viewer endpoints (mesh, properties, wells) |
| `keywords.py` | `/api/keywords` | Merged keyword catalogue (Stage 3.4) |
| `lint.py` | `/api/lint` | Lint saved deck |
| `results.py` | `/api/results` | KPI extraction, time-series plots |
| `run.py` | `/api/run` | Background simulation jobs |
| `settings.py` | `/api/settings` | User settings (LLM keys, paths) |

## Keywords route (Stage 3.4)

`GET /api/keywords` returns the merged catalogue (fixture ∪ ERM, 1916+
keywords). Per-process cache in module global `_CACHE`; restart server
to pick up catalogue updates. Used by Monaco editor autocomplete +
hover (see `frontend/src/components/opmCompletions.ts`).

## Build route - correlation threading (2026-08-04)

`POST /api/build` accepts `fluid.correlation` (Literal["Standing",
"VasquezBeggs", "AlMarhoun"] | None) in the request body. The route
constructs `FluidDescriptor(correlation=request.fluid.correlation or
"Standing")` and passes it to the builder; null defaults to Standing
to preserve pre-existing behaviour. Invalid values are rejected by
Pydantic with HTTP 422.

## Test Contracts
- `tests/integration/test_api_*.py` covers each route
- Test client fixture in `tests/conftest.py`

## Future / Plan
- CORS preflight cache
- Per-route authn once `Authentication` (api/context.md §3) lands
