from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterator

import pytest

from meetingai_backend.media.assets import load_media_assets
from meetingai_backend.settings import Settings, set_settings
from meetingai_backend.tasks.ingest import process_uploaded_video
from meetingai_backend.tasks.transcribe import transcribe_audio_for_job
from meetingai_backend.transcription import ChunkTranscriptionResult
from meetingai_backend.transcription.segments import load_transcript_segments


@pytest.fixture(autouse=True)
def reset_settings() -> Iterator[None]:
    set_settings(None)
    yield
    set_settings(None)


def _copy_sample_video(tmp_path: Path) -> tuple[str, Path]:
    sample_path = Path(__file__).parent / "data" / "2025-05-23 13-03-45.mov"
    if not sample_path.exists():
        pytest.skip("sample video not available for integration test")

    job_id = "job-integration"
    job_dir = tmp_path / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    destination = job_dir / sample_path.name
    shutil.copy(sample_path, destination)
    return job_id, destination


def test_video_upload_to_transcript_segments(tmp_path: Path, monkeypatch) -> None:
    job_id, video_path = _copy_sample_video(tmp_path)

    settings = Settings(
        upload_root=tmp_path,
        redis_url="redis://localhost:6379/0",
        job_queue_name="meetingai:jobs",
        job_timeout_seconds=900,
        ffmpeg_path="ffmpeg",
        openai_api_key="test-api-key",
    )
    set_settings(settings)

    if shutil.which(settings.ffmpeg_path) is None:
        pytest.skip("ffmpeg binary is not available for integration test")

    ingest_result = process_uploaded_video(job_id=job_id, source_path=str(video_path))

    audio_path = Path(ingest_result["audio_path"])
    assert audio_path.exists()

    chunk_paths = [Path(path) for path in ingest_result["audio_chunks"]]
    assert chunk_paths and all(path.exists() for path in chunk_paths)

    job_directory = video_path.parent
    assets = load_media_assets(job_directory)
    chunk_assets = [asset for asset in assets if asset.kind == "audio_chunk"]
    assert len(chunk_assets) == len(chunk_paths)

    def fake_transcribe_audio_chunks(
        chunk_assets_param,
        *,
        config,
        language,
        prompt,
        request_fn=None,
        sleep=None,
    ):
        results: list[ChunkTranscriptionResult] = []
        for index, asset in enumerate(chunk_assets_param):
            results.append(
                ChunkTranscriptionResult(
                    asset_id=asset.asset_id,
                    text=f"chunk-{index}",
                    start_ms=asset.start_ms,
                    end_ms=asset.end_ms,
                    duration_ms=asset.duration_ms,
                    language="ja",
                    response={
                        "segments": [
                            {
                                "start": 0.0,
                                "end": asset.duration_ms / 1000.0,
                                "text": f"segment-{index}",
                            }
                        ]
                    },
                )
            )
        return results

    monkeypatch.setattr(
        "meetingai_backend.tasks.transcribe.transcribe_audio_chunks",
        fake_transcribe_audio_chunks,
    )

    transcription_result = transcribe_audio_for_job(
        job_id=job_id,
        job_directory=str(job_directory),
    )

    assert transcription_result["job_id"] == job_id
    assert transcription_result["chunk_count"] == len(chunk_assets)
    assert transcription_result["segment_count"] == len(chunk_assets)
    assert transcription_result["languages"] == ["ja"]

    segments_path = Path(transcription_result["segments_path"])
    assert segments_path.exists()

    segments = load_transcript_segments(job_directory)
    assert len(segments) == len(chunk_assets)
    assert segments[0].text == "segment-0"
