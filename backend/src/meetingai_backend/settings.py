# Application-wide configuration helpers.

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_SETTINGS_CACHE: Settings | None = None


@dataclass(slots=True)
class Settings:
    """Runtime configuration derived from environment variables."""

    upload_root: Path
    redis_url: str
    job_queue_name: str
    job_timeout_seconds: int
    ffmpeg_path: str
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_transcription_model: str = "gpt-4o-transcribe"
    openai_user_agent: str | None = "MeetingAI/0.1"
    openai_request_timeout_seconds: float = 300.0
    openai_max_attempts: int = 3
    openai_retry_backoff_seconds: float = 1.0
    openai_max_retry_backoff_seconds: float | None = 30.0
    openai_requests_per_minute: int | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables with sensible defaults."""
        root_override = os.getenv("MEETINGAI_UPLOAD_DIR")
        if root_override:
            upload_root = Path(root_override).expanduser()
        else:
            upload_root = Path(__file__).resolve().parents[3] / "storage" / "uploads"

        redis_url = os.getenv("MEETINGAI_REDIS_URL", "redis://localhost:6379/0")
        job_queue_name = os.getenv("MEETINGAI_JOB_QUEUE_NAME", "meetingai:jobs")
        timeout_raw = os.getenv("MEETINGAI_JOB_TIMEOUT", "900")
        ffmpeg_path = os.getenv("MEETINGAI_FFMPEG_PATH", "ffmpeg")

        try:
            job_timeout_seconds = int(timeout_raw)
        except ValueError as exc:
            raise ValueError(
                "MEETINGAI_JOB_TIMEOUT must be an integer representing seconds."
            ) from exc

        openai_api_key = os.getenv("OPENAI_API_KEY")
        openai_base_url = os.getenv(
            "MEETINGAI_OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
        openai_model = os.getenv("MEETINGAI_TRANSCRIBE_MODEL", "gpt-4o-transcribe")
        openai_user_agent = (
            os.getenv("MEETINGAI_TRANSCRIBE_USER_AGENT", "MeetingAI/0.1") or None
        )

        timeout_raw = os.getenv("MEETINGAI_TRANSCRIBE_TIMEOUT", "300")
        max_attempts_raw = os.getenv("MEETINGAI_TRANSCRIBE_MAX_ATTEMPTS", "3")
        retry_backoff_raw = os.getenv("MEETINGAI_TRANSCRIBE_BACKOFF_SECONDS", "1.0")
        max_retry_backoff_raw = os.getenv(
            "MEETINGAI_TRANSCRIBE_MAX_BACKOFF_SECONDS", "30.0"
        )
        requests_per_minute_raw = os.getenv("MEETINGAI_TRANSCRIBE_REQUESTS_PER_MINUTE")

        try:
            request_timeout_seconds = float(timeout_raw)
        except ValueError as exc:
            raise ValueError("MEETINGAI_TRANSCRIBE_TIMEOUT must be numeric.") from exc

        try:
            max_attempts = int(max_attempts_raw)
        except ValueError as exc:
            raise ValueError(
                "MEETINGAI_TRANSCRIBE_MAX_ATTEMPTS must be an integer."
            ) from exc

        try:
            retry_backoff_seconds = float(retry_backoff_raw)
        except ValueError as exc:
            raise ValueError(
                "MEETINGAI_TRANSCRIBE_BACKOFF_SECONDS must be numeric."
            ) from exc

        max_retry_backoff_seconds: float | None
        if max_retry_backoff_raw in (None, "", "none", "None"):
            max_retry_backoff_seconds = None
        else:
            try:
                max_retry_backoff_seconds = float(max_retry_backoff_raw)
            except ValueError as exc:
                raise ValueError(
                    "MEETINGAI_TRANSCRIBE_MAX_BACKOFF_SECONDS must be numeric or empty."
                ) from exc

        requests_per_minute: int | None
        if requests_per_minute_raw in (None, "", "none", "None"):
            requests_per_minute = None
        else:
            try:
                requests_per_minute = int(requests_per_minute_raw)
            except ValueError as exc:
                raise ValueError(
                    "MEETINGAI_TRANSCRIBE_REQUESTS_PER_MINUTE must be an integer."
                ) from exc

        return cls(
            upload_root=upload_root.resolve(strict=False),
            redis_url=redis_url,
            job_queue_name=job_queue_name,
            job_timeout_seconds=job_timeout_seconds,
            ffmpeg_path=ffmpeg_path,
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            openai_transcription_model=openai_model,
            openai_user_agent=openai_user_agent,
            openai_request_timeout_seconds=request_timeout_seconds,
            openai_max_attempts=max_attempts,
            openai_retry_backoff_seconds=retry_backoff_seconds,
            openai_max_retry_backoff_seconds=max_retry_backoff_seconds,
            openai_requests_per_minute=requests_per_minute,
        )


def get_settings() -> Settings:
    """Return cached settings instance, constructing it on first access."""
    global _SETTINGS_CACHE

    if _SETTINGS_CACHE is None:
        _SETTINGS_CACHE = Settings.from_env()

    return _SETTINGS_CACHE


def set_settings(settings: Settings | None) -> None:
    """Override the cached settings value (mainly intended for tests)."""
    global _SETTINGS_CACHE
    _SETTINGS_CACHE = settings


__all__ = ["Settings", "get_settings", "set_settings"]
