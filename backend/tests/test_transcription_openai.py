from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from meetingai_backend.media import MediaAsset
from meetingai_backend.transcription import (
    OpenAITranscriptionConfig,
    TranscriptionError,
    transcribe_audio_chunks,
)
from meetingai_backend.transcription.openai import ChunkTranscriptionResult


def _make_chunk_asset(tmp_path: Path, *, name: str, order: int) -> MediaAsset:
    chunk_path = tmp_path / name
    chunk_path.write_bytes(b"audio-data")
    start_ms = order * 1000
    duration_ms = 1000
    return MediaAsset(
        asset_id=f"asset-{order}",
        job_id="job-123",
        kind="audio_chunk",
        path=chunk_path,
        order=order,
        duration_ms=duration_ms,
        start_ms=start_ms,
        end_ms=start_ms + duration_ms,
        sample_rate=16_000,
        channels=1,
        bit_depth=16,
        parent_asset_id="master-1",
        extra={},
    )


def test_transcribe_audio_chunks_success(tmp_path) -> None:
    assets = [
        _make_chunk_asset(tmp_path, name="chunk-0.wav", order=0),
        _make_chunk_asset(tmp_path, name="chunk-1.wav", order=1),
    ]

    calls: list[Path] = []

    def request_fn(*, file_path: Path, config, language, prompt) -> dict[str, object]:
        calls.append(file_path)
        return {"text": f"transcribed-{file_path.name}", "language": "ja"}

    config = OpenAITranscriptionConfig(api_key="test-key", requests_per_minute=None)
    results = transcribe_audio_chunks(
        assets,
        config=config,
        language="ja",
        prompt=None,
        request_fn=request_fn,  # type: ignore[arg-type]
    )

    assert isinstance(results[0], ChunkTranscriptionResult)
    assert [result.text for result in results] == [
        "transcribed-chunk-0.wav",
        "transcribed-chunk-1.wav",
    ]
    assert calls == [asset.path for asset in assets]


def test_transcribe_audio_chunks_retries_on_retriable_error(
    monkeypatch, tmp_path
) -> None:
    asset = _make_chunk_asset(tmp_path, name="chunk-0.wav", order=0)
    request = httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")
    response = httpx.Response(429, request=request, headers={"Retry-After": "2"})
    error = httpx.HTTPStatusError("rate limited", request=request, response=response)

    attempts = 0

    def request_fn(*, file_path: Path, config, language, prompt) -> dict[str, object]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise error
        return {"text": "ok", "language": "en"}

    sleep_calls: list[float] = []

    def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    config = OpenAITranscriptionConfig(
        api_key="test-key",
        max_attempts=3,
        retry_backoff_seconds=1.0,
        max_retry_backoff_seconds=10.0,
    )

    results = transcribe_audio_chunks(
        [asset],
        config=config,
        request_fn=request_fn,  # type: ignore[arg-type]
        sleep=fake_sleep,
    )

    assert attempts == 2
    assert sleep_calls == [pytest.approx(2.0)]
    assert results[0].text == "ok"


def test_transcribe_audio_chunks_raises_after_max_attempts(tmp_path) -> None:
    asset = _make_chunk_asset(tmp_path, name="chunk-0.wav", order=0)
    request = httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")

    def request_fn(*, file_path: Path, config, language, prompt):
        raise httpx.RequestError("network issue", request=request)

    config = OpenAITranscriptionConfig(api_key="test-key", max_attempts=2)

    with pytest.raises(TranscriptionError) as exc_info:
        transcribe_audio_chunks(
            [asset],
            config=config,
            request_fn=request_fn,  # type: ignore[arg-type]
        )

    err = exc_info.value
    assert err.asset_id == asset.asset_id
    assert "network" in str(err.__cause__)


def test_transcribe_audio_chunks_rate_limit_enforced(monkeypatch, tmp_path) -> None:
    import meetingai_backend.transcription.openai as module

    current_time = 0.0

    def fake_monotonic() -> float:
        return current_time

    monkeypatch.setattr(module.time, "monotonic", fake_monotonic)

    assets = [
        _make_chunk_asset(tmp_path, name="chunk-0.wav", order=0),
        _make_chunk_asset(tmp_path, name="chunk-1.wav", order=1),
    ]

    sleep_calls: list[float] = []

    def fake_sleep(duration: float) -> None:
        sleep_calls.append(duration)
        nonlocal current_time
        current_time += duration

    config = OpenAITranscriptionConfig(api_key="test-key", requests_per_minute=120)
    results = transcribe_audio_chunks(
        assets,
        config=config,
        request_fn=lambda **_: {"text": "ok", "language": "en"},  # type: ignore[arg-type]
        sleep=fake_sleep,
    )

    assert len(results) == 2
    assert sleep_calls == [pytest.approx(0.5, abs=1e-3)]
