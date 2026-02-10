# Application factory and FastAPI setup.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import health, jobs, meetings, videos
from .settings import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(title="MeetingAI Backend", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    settings = get_settings()
    settings.upload_root.mkdir(parents=True, exist_ok=True)
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(jobs.router)
    app.include_router(meetings.router)
    app.include_router(videos.router)
    return app
