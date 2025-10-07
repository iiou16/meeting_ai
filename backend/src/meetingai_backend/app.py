# Application factory and FastAPI setup.

from fastapi import FastAPI

from .routers import health, videos
from .settings import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(title="MeetingAI Backend", version="0.1.0")

    settings = get_settings()
    settings.upload_root.mkdir(parents=True, exist_ok=True)
    app.state.settings = settings

    app.include_router(health.router)
    app.include_router(videos.router)
    return app
