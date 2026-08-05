"""FastAPI application factory with CORS, static mount, and router inclusion."""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from opm_ai.api.routes import build, decks, files, grid, lint, run, results, chat, explainer, upload
from opm_ai.api.routes import keywords as keywords_routes
from opm_ai.api.routes import settings as settings_routes
from opm_ai.api.session_store import get_session_store
from opm_ai.settings import settings


class SPAStaticFiles(StaticFiles):
    """Serve index.html for unknown extension-less paths so client-side
    routes deep-link. Paths with a file extension (e.g. /assets/x.js) still
    404 so broken builds fail loudly instead of parsing HTML as JS."""

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or "." in Path(path).name:
                raise
            return await super().get_response("index.html", scope)
        if response.status_code == 404 and "." not in Path(path).name:
            response = await super().get_response("index.html", scope)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown."""
    # Initialize session store on app state
    session_store = get_session_store()
    yield
    # Cleanup on shutdown
    session_store.clear()


def create_app() -> FastAPI:
    """
    Factory returning a FastAPI instance with:
    - CORS allow_origins = ["http://localhost:5173"] (Vite default)
    - Optional static mount of frontend/dist at "/" when built artefacts exist
    - Routers included: build, lint, run, results, chat
    """
    app = FastAPI(
        title="OPM AI API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS for Vite dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers with /api prefix
    app.include_router(build.router, prefix="/api")
    app.include_router(decks.router, prefix="/api")
    app.include_router(files.router, prefix="/api")
    app.include_router(lint.router, prefix="/api")
    app.include_router(run.router, prefix="/api")
    app.include_router(upload.router, prefix="/api")
    # grid before results: both hang off /results/{job_id}, and registering the
    # literal /grid/... paths first keeps them unambiguous whatever results.py
    # grows later.
    app.include_router(grid.router, prefix="/api")
    app.include_router(results.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(explainer.router, prefix="/api")
    app.include_router(settings_routes.router, prefix="/api")
    app.include_router(keywords_routes.router, prefix="/api")

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    # Optional static mount of the built frontend at "/" for production.
    # Must be AFTER all /api routes so API routes take precedence.
    # Docker bakes the bundle at /app/static; local dev builds to frontend/dist.
    repo_root = Path(__file__).resolve().parents[2]
    for candidate in (Path("/app/static"), repo_root / "frontend" / "dist"):
        if (candidate / "index.html").exists():
            app.mount("/", SPAStaticFiles(directory=candidate, html=True), name="frontend")
            break

    return app