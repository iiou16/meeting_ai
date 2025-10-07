from __future__ import annotations

# Tests load .env manually so the integration flow runs without shell exporting.
import os
import shutil
from pathlib import Path
from typing import Iterator

import pytest

from meetingai_backend.media.assets import load_media_assets
from meetingai_backend.settings import Settings, set_settings
from meetingai_backend.tasks.ingest import process_uploaded_video
from meetingai_backend.tasks.transcribe import transcribe_audio_for_job
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


def _load_dotenv_if_needed() -> None:
    """Populate environment variables from the repository's .env file."""
    project_root = Path(__file__).resolve().parents[2]
    dotenv_path = project_root / ".env"
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        cleaned = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, cleaned)


def test_video_upload_to_transcript_segments(tmp_path: Path) -> None:
    job_id, video_path = _copy_sample_video(tmp_path)

    _load_dotenv_if_needed()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.fail("OPENAI_API_KEY is not configured for integration test")

    settings = Settings(
        upload_root=tmp_path,
        redis_url="redis://localhost:6379/0",
        job_queue_name="meetingai:jobs",
        job_timeout_seconds=900,
        ffmpeg_path="ffmpeg",
        openai_api_key=api_key,
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

    transcription_result = transcribe_audio_for_job(
        job_id=job_id,
        job_directory=str(job_directory),
    )

    assert transcription_result["job_id"] == job_id
    assert transcription_result["chunk_count"] == len(chunk_assets)

    segments_path = Path(transcription_result["segments_path"])
    assert segments_path.exists()

    segments = load_transcript_segments(job_directory)
    assert segments
    assert transcription_result["segment_count"] == len(segments)
    assert all(segment.text.strip() for segment in segments)

    reported_languages = transcription_result["languages"]
    assert isinstance(reported_languages, list)
    detected_languages = sorted(
        {segment.language for segment in segments if segment.language}
    )
    assert reported_languages == detected_languages
