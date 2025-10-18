from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from meetingai_backend.media.assets import MediaAsset, dump_media_assets
from meetingai_backend.settings import Settings, set_settings
from meetingai_backend.tasks.transcribe import transcribe_audio_for_job
from meetingai_backend.transcription.segments import load_transcript_segments


@pytest.fixture(autouse=True)
def reset_settings() -> Iterator[None]:
    set_settings(None)
    yield
    set_settings(None)


def _prepare_job_directory(tmp_path: Path) -> tuple[Path, MediaAsset, MediaAsset]:
    job_dir = tmp_path / "job-001"
    chunk_dir = job_dir / "audio_chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)

    master_asset = MediaAsset(
        asset_id="master-asset",
        job_id="job-001",
        kind="audio_master",
        path=job_dir / "master.wav",
        order=-1,
        duration_ms=4_000,
        start_ms=0,
        end_ms=4_000,
        sample_rate=16_000,
        channels=1,
        bit_depth=16,
        parent_asset_id=None,
        extra={},
    )

    chunk_path = chunk_dir / "chunk_0000.wav"
    chunk_path.write_bytes(b"audio")
    chunk_asset = MediaAsset(
        asset_id="chunk-asset",
        job_id="job-001",
        kind="audio_chunk",
        path=chunk_path,
        order=0,
        duration_ms=2_000,
        start_ms=0,
        end_ms=2_000,
        sample_rate=16_000,
        channels=1,
        bit_depth=16,
        parent_asset_id=master_asset.asset_id,
        extra={},
    )

    dump_media_assets(job_dir, [master_asset, chunk_asset])
    return job_dir, master_asset, chunk_asset


def test_transcribe_audio_for_job_persists_segments(
    tmp_path: Path, monkeypatch
) -> None:
    job_dir, _master, chunk_asset = _prepare_job_directory(tmp_path)

    settings = Settings(
        upload_root=tmp_path,
        redis_url="redis://localhost:6379/0",
        job_queue_name="meetingai:jobs",
        job_timeout_seconds=900,
        ffmpeg_path="ffmpeg",
        openai_api_key="test-key",
    )
    set_settings(settings)

    def fake_request_fn(
        *, file_path: Path, config, language, prompt
    ) -> dict[str, object]:
        assert file_path == chunk_asset.path
        assert config.api_key == "test-key"
        return {
            "text": "こんにちは 世界",
            "language": "ja",
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "こんにちは", "speaker": "A"},
                {"start": 1.0, "end": 2.0, "text": "世界"},
            ],
        }

    enqueued: dict[str, str] = {}

    monkeypatch.setattr(
        "meetingai_backend.tasks.transcribe.get_job_queue",
        lambda _: object(),
    )

    def fake_enqueue_summary_job(*, queue, job_id, job_directory):
        enqueued["job_id"] = job_id
        enqueued["job_directory"] = job_directory

    monkeypatch.setattr(
        "meetingai_backend.tasks.transcribe.enqueue_summary_job",
        fake_enqueue_summary_job,
    )

    result = transcribe_audio_for_job(
        job_id="job-001",
        job_directory=str(job_dir),
        request_fn=fake_request_fn,  # type: ignore[arg-type]
        sleep=lambda _: None,
    )

    assert result["job_id"] == "job-001"
    assert result["chunk_count"] == 1
    assert result["segment_count"] == 2
    assert result["languages"] == ["ja"]

    segments_path = Path(result["segments_path"])
    assert segments_path.exists()

    segments = load_transcript_segments(job_dir)
    assert len(segments) == 2
    assert segments[0].text == "こんにちは"
    assert segments[0].speaker_label == "A"
    assert segments[1].start_ms == 1_000
    assert segments[1].end_ms == 2_000
    assert enqueued["job_id"] == "job-001"
    assert enqueued["job_directory"] == str(job_dir)


def test_transcribe_audio_for_job_requires_api_key(tmp_path: Path) -> None:
    job_dir, *_ = _prepare_job_directory(tmp_path)

    settings = Settings(
        upload_root=tmp_path,
        redis_url="redis://localhost:6379/0",
        job_queue_name="meetingai:jobs",
        job_timeout_seconds=900,
        ffmpeg_path="ffmpeg",
        openai_api_key=None,
    )
    set_settings(settings)

    with pytest.raises(RuntimeError):
        transcribe_audio_for_job(
            job_id="job-001",
            job_directory=str(job_dir),
            request_fn=lambda **_: {},  # type: ignore[arg-type]
        )
