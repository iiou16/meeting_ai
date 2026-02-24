"""Tests for meetingai_backend.app module (application factory)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.routing import BaseRoute

from meetingai_backend.app import create_app
from meetingai_backend.settings import Settings, set_settings


@pytest.fixture(autouse=True)
def _reset_settings() -> Iterator[None]:
    set_settings(None)
    yield
    set_settings(None)


def _inject_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        upload_root=tmp_path / "uploads",
        redis_url="redis://localhost:6379/0",
        job_queue_name="test:jobs",
        job_timeout_seconds=60,
        ffmpeg_path="ffmpeg",
    )
    set_settings(settings)
    return settings


def _route_paths(routes: list[BaseRoute]) -> list[str]:
    return [getattr(r, "path", None) for r in routes if hasattr(r, "path")]


class TestAppFactory:
    def test_create_app_returns_fastapi_instance(self, tmp_path: Path) -> None:
        _inject_settings(tmp_path)
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_title_and_version(self, tmp_path: Path) -> None:
        _inject_settings(tmp_path)
        app = create_app()
        assert app.title == "MeetingAI Backend"
        assert app.version == "0.1.0"

    def test_all_routers_registered(self, tmp_path: Path) -> None:
        _inject_settings(tmp_path)
        app = create_app()
        paths = _route_paths(app.routes)
        assert "/health" in paths
        assert "/api/jobs" in paths
        assert "/api/meetings/{job_id}" in paths
        assert "/api/videos" in paths

    def test_cors_middleware_configured_with_correct_options(
        self, tmp_path: Path
    ) -> None:
        _inject_settings(tmp_path)
        app = create_app()
        cors_middleware = None
        for m in app.user_middleware:
            if getattr(m, "cls", None) is CORSMiddleware:
                cors_middleware = m
                break
        assert cors_middleware is not None
        assert cors_middleware.kwargs["allow_origins"] == ["*"]
        assert cors_middleware.kwargs["allow_credentials"] is False
        assert cors_middleware.kwargs["allow_methods"] == ["*"]
        assert cors_middleware.kwargs["allow_headers"] == ["*"]

    def test_settings_stored_in_app_state(self, tmp_path: Path) -> None:
        settings = _inject_settings(tmp_path)
        app = create_app()
        assert app.state.settings is settings

    def test_upload_root_directory_created(self, tmp_path: Path) -> None:
        settings = _inject_settings(tmp_path)
        assert not settings.upload_root.exists()
        create_app()
        assert settings.upload_root.is_dir()
