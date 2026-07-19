"""FastAPI application factory with CORS, static mount, and router inclusion."""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from opm_ai.api.routes import build, lint, run, results, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown."""
    # Initialize job store and session store on app state
    app.state.jobs = {}
    app.state.sessions = {}
    yield
    # Cleanup on shutdown
    app.state.jobs.clear()
    app.state.sessions.clear()


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
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers with /api prefix
    app.include_router(build.router, prefix="/api")
    app.include_router(lint.router, prefix="/api")
    app.include_router(run.router, prefix="/api")
    app.include_router(results.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")

    # Optional static mount of frontend/dist at "/" for production
    frontend_dist = Path("frontend/dist")
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    return app