"""Helpers for calling the OpenAI GPT-4o transcription API."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence

import httpx

from ..media import MediaAsset

logger = logging.getLogger(__name__)

_EXTENSION_MIME_TYPES: dict[str, str] = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".mp4": "audio/mp4",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
}


class TranscriptionError(RuntimeError):
    """Raised when a transcription request ultimately fails."""

    def __init__(
        self, message: str, *, asset_id: str, status_code: int | None = None
    ) -> None:
        super().__init__(message)
        self.asset_id = asset_id
        self.status_code = status_code


@dataclass(slots=True)
class OpenAITranscriptionConfig:
    """Configuration for interacting with the OpenAI transcription endpoint."""

    api_key: str
    model: str = "gpt-4o-transcribe-diarize"
    base_url: str = "https://api.openai.com/v1"
    request_timeout_seconds: float = 300.0
    max_attempts: int = 3
    retry_backoff_seconds: float = 1.0
    max_retry_backoff_seconds: float | None = 30.0
    requests_per_minute: int | None = None
    user_agent: str | None = "MeetingAI/0.1"

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("api_key must be provided for OpenAI transcription.")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive.")
        if self.retry_backoff_seconds <= 0:
            raise ValueError("retry_backoff_seconds must be positive.")
        if (
            self.max_retry_backoff_seconds is not None
            and self.max_retry_backoff_seconds <= 0
        ):
            raise ValueError(
                "max_retry_backoff_seconds must be positive when provided."
            )


@dataclass(slots=True)
class ChunkTranscriptionResult:
    """Transcription data returned for a single audio chunk."""

    asset_id: str
    text: str
    start_ms: int
    end_ms: int
    duration_ms: int
    language: str | None
    response: dict[str, object]


class ChunkRequestFn(Protocol):
    """Callable responsible for executing a single transcription request."""

    def __call__(
        self,
        *,
        file_path: Path,
        config: OpenAITranscriptionConfig,
        language: str | None,
        prompt: str | None,
    ) -> dict[str, object]: ...


class _RateLimiter:
    """Simple rate limiter that enforces a minimum interval between requests."""

    def __init__(
        self,
        *,
        min_interval_seconds: float,
        sleep: Callable[[float], None],
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._min_interval_seconds = max(0.0, min_interval_seconds)
        self._sleep = sleep
        self._now = now
        self._last_request_at: float | None = None

    def acquire(self) -> None:
        if self._min_interval_seconds <= 0:
            return

        current = self._now()
        if self._last_request_at is not None:
            elapsed = current - self._last_request_at
            remaining = self._min_interval_seconds - elapsed
            if remaining > 0:
                self._sleep(remaining)
                current = self._now()

        self._last_request_at = current

    @classmethod
    def from_config(
        cls, config: OpenAITranscriptionConfig, *, sleep: Callable[[float], None]
    ) -> "_RateLimiter":
        requests_per_minute = config.requests_per_minute
        if requests_per_minute is None or requests_per_minute <= 0:
            interval = 0.0
        else:
            interval = 60.0 / requests_per_minute
        return cls(min_interval_seconds=interval, sleep=sleep)


_RETRIABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


def transcribe_audio_chunks(
    chunk_assets: Sequence[MediaAsset],
    *,
    config: OpenAITranscriptionConfig,
    language: str | None = None,
    prompt: str | None = None,
    request_fn: ChunkRequestFn | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> list[ChunkTranscriptionResult]:
    """Transcribe the provided audio chunks with retries and basic rate limiting."""
    if not chunk_assets:
        return []

    rate_limiter = _RateLimiter.from_config(config, sleep=sleep)
    perform_request = request_fn or _call_openai_transcription_api
    results: list[ChunkTranscriptionResult] = []

    for chunk_index, asset in enumerate(chunk_assets):
        if not asset.path.exists():
            raise FileNotFoundError(f"audio chunk file does not exist: {asset.path}")

        attempt = 0
        last_exception: Exception | None = None

        while attempt < config.max_attempts:
            attempt += 1
            rate_limiter.acquire()

            logger.info(
                "Transcribing chunk %d/%d (asset=%s, attempt=%d/%d)",
                chunk_index + 1,
                len(chunk_assets),
                asset.asset_id,
                attempt,
                config.max_attempts,
            )
            request_start = time.monotonic()

            try:
                payload = perform_request(
                    file_path=asset.path,
                    config=config,
                    language=language,
                    prompt=prompt,
                )
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code if exc.response is not None else None
                error_text = None
                if exc.response is not None:
                    try:
                        error_text = exc.response.text
                    except (AttributeError, UnicodeDecodeError) as read_exc:
                        logger.warning(
                            "Could not read error response text: %s", read_exc
                        )
                if status in _RETRIABLE_STATUS and attempt < config.max_attempts:
                    delay = _select_retry_delay(
                        attempt=attempt,
                        config=config,
                        response=exc.response,
                    )
                    sleep(delay)
                    last_exception = exc
                    continue

                raise TranscriptionError(
                    f"transcription failed with status {status}: {error_text}",
                    asset_id=asset.asset_id,
                    status_code=status,
                ) from exc
            except httpx.RequestError as exc:
                if attempt < config.max_attempts:
                    delay = _select_retry_delay(
                        attempt=attempt,
                        config=config,
                        response=None,
                    )
                    sleep(delay)
                    last_exception = exc
                    continue

                raise TranscriptionError(
                    "transcription request failed due to network error",
                    asset_id=asset.asset_id,
                    status_code=None,
                ) from exc
            except Exception as exc:
                raise TranscriptionError(
                    "unexpected error during transcription",
                    asset_id=asset.asset_id,
                    status_code=None,
                ) from exc

            elapsed = time.monotonic() - request_start
            logger.info(
                "Chunk %d/%d transcribed in %.1fs (asset=%s)",
                chunk_index + 1,
                len(chunk_assets),
                elapsed,
                asset.asset_id,
            )

            text = _extract_transcript_text(payload, asset_id=asset.asset_id)
            detected_language = _extract_language(payload)

            results.append(
                ChunkTranscriptionResult(
                    asset_id=asset.asset_id,
                    text=text,
                    start_ms=asset.start_ms,
                    end_ms=asset.end_ms,
                    duration_ms=asset.duration_ms,
                    language=detected_language or language,
                    response=(
                        dict(payload) if isinstance(payload, dict) else {"raw": payload}
                    ),
                )
            )
            break
        else:
            raise TranscriptionError(
                "exhausted retries while transcribing audio chunk",
                asset_id=asset.asset_id,
                status_code=None,
            ) from last_exception

    return results


def _call_openai_transcription_api(
    *,
    file_path: Path,
    config: OpenAITranscriptionConfig,
    language: str | None,
    prompt: str | None,
) -> dict[str, object]:
    url = f"{config.base_url.rstrip('/')}/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
    }
    if config.user_agent:
        headers["User-Agent"] = config.user_agent

    data: dict[str, str] = {"model": config.model}
    normalized_model = config.model.lower()
    if normalized_model.endswith("-diarize"):
        data["response_format"] = "diarized_json"
        data["chunking_strategy"] = json.dumps({"type": "server_vad"})
    elif "gpt-4o-transcribe" in normalized_model:
        # gpt-4o-transcribe supports verbose_json with segment granularity.
        # Note: gpt-4o-transcribe-diarize rejects verbose_json (handled in the branch above).
        data["response_format"] = "verbose_json"
        data["timestamp_granularities[]"] = "segment"
    else:
        data["response_format"] = "verbose_json"
        data["timestamp_granularities[]"] = "segment"
    if language:
        data["language"] = language
    if prompt:
        data["prompt"] = prompt

    extension = file_path.suffix.lower()
    if extension not in _EXTENSION_MIME_TYPES:
        raise ValueError(
            f"Unsupported audio file extension '{extension}' for file {file_path}. "
            f"Supported extensions: {sorted(_EXTENSION_MIME_TYPES.keys())}"
        )
    mime_type = _EXTENSION_MIME_TYPES[extension]

    with file_path.open("rb") as audio_file:
        response = httpx.post(
            url,
            headers=headers,
            data=data,
            files={"file": (file_path.name, audio_file, mime_type)},
            timeout=config.request_timeout_seconds,
        )

    response.raise_for_status()

    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(
            "OpenAI transcription API returned unexpected response format."
        )

    return payload


def _extract_transcript_text(payload: dict[str, object], *, asset_id: str) -> str:
    if "text" in payload:
        text = payload["text"]
        if isinstance(text, str):
            return text
    if "segments" in payload and isinstance(payload["segments"], list):
        segments = payload["segments"]
        collected = []
        for entry in segments:
            if isinstance(entry, dict) and "text" in entry:
                segment_text = entry["text"]
                if isinstance(segment_text, str):
                    collected.append(segment_text)
        if collected:
            return " ".join(collected)
    raise TranscriptionError(
        "transcription response did not contain text field",
        asset_id=asset_id,
        status_code=None,
    )


def _extract_language(payload: dict[str, object]) -> str | None:
    if "language" in payload:
        language = payload["language"]
        if isinstance(language, str):
            return language
    if "metadata" in payload:
        metadata = payload["metadata"]
        if isinstance(metadata, dict) and "language" in metadata:
            detected = metadata["language"]
            if isinstance(detected, str):
                return detected
    return None


def _select_retry_delay(
    *,
    attempt: int,
    config: OpenAITranscriptionConfig,
    response: httpx.Response | None,
) -> float:
    base_delay = config.retry_backoff_seconds * (2 ** (attempt - 1))
    retry_after = (
        _parse_retry_after_seconds(response.headers) if response is not None else None
    )
    delay = base_delay
    if retry_after is not None:
        delay = max(delay, retry_after)
    if config.max_retry_backoff_seconds is not None:
        delay = min(delay, config.max_retry_backoff_seconds)
    return delay


def _parse_retry_after_seconds(headers: Mapping[str, str]) -> float | None:
    if "Retry-After" not in headers:
        return None
    raw_value = headers["Retry-After"]

    value = raw_value.strip()
    try:
        seconds = float(value)
    except ValueError:
        return _parse_retry_after_date(value)

    if seconds < 0:
        return None
    return seconds


def _parse_retry_after_date(value: str) -> float | None:
    try:
        from email.utils import parsedate_to_datetime
    except ImportError:  # pragma: no cover - fallback for alternative runtimes
        return None

    parsed = parsedate_to_datetime(value)
    if parsed is None:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    delta = (parsed - now).total_seconds()
    if delta <= 0:
        return None
    return delta


__all__ = [
    "ChunkTranscriptionResult",
    "OpenAITranscriptionConfig",
    "TranscriptionError",
    "transcribe_audio_chunks",
]
