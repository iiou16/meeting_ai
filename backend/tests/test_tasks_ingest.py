from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import pytest

from meetingai_backend.media.assets import MediaAsset
from meetingai_backend.media.chunking import AudioChunkSpec
from meetingai_backend.settings import Settings, set_settings
from meetingai_backend.tasks.ingest import process_uploaded_video


@pytest.fixture(autouse=True)
def reset_settings() -> Iterator[None]:
    set_settings(None)
    yield
    set_settings(None)


def test_process_uploaded_video_extracts_audio(monkeypatch, tmp_path) -> None:
    video = tmp_path / "recording.mp4"
    video.write_bytes(b"binary-video")

    def fake_extract_audio(path: Path, *, config):
        assert config.ffmpeg_path == "ffmpeg-test"
        destination = path.with_suffix(".wav")
        destination.write_bytes(b"audio")
        return destination

    monkeypatch.setattr(
        "meetingai_backend.tasks.ingest.extract_audio_to_wav",
        fake_extract_audio,
    )

    settings = Settings(
        upload_root=tmp_path,
        redis_url="redis://localhost:6379/0",
        job_queue_name="meetingai:jobs",
        job_timeout_seconds=900,
        ffmpeg_path="ffmpeg-test",
    )
    set_settings(settings)

    def fake_split(
        audio_path: Path,
        *,
        job_id: str,
        chunk_duration_seconds: int = 900,
        parent_asset_id,
        output_dir: Path,
    ):
        output_dir.mkdir(parents=True, exist_ok=True)
        chunk_path = output_dir / "chunk_0000.wav"
        chunk_path.write_bytes(b"chunk-audio")
        chunk_asset = MediaAsset(
            asset_id="chunk-asset",
            job_id=job_id,
            kind="audio_chunk",
            path=chunk_path.resolve(),
            order=0,
            duration_ms=480,
            start_ms=0,
            end_ms=480,
            sample_rate=16_000,
            channels=1,
            bit_depth=16,
            parent_asset_id=parent_asset_id,
            extra={},
        )
        return [AudioChunkSpec(asset=chunk_asset, path=chunk_path)]

    monkeypatch.setattr(
        "meetingai_backend.tasks.ingest.split_wav_into_chunks",
        fake_split,
    )

    result = process_uploaded_video(job_id="abc123", source_path=str(video))

    assert result["job_id"] == "abc123"
    assert Path(result["source_path"]).resolve() == video.resolve()
    audio_path = Path(result["audio_path"])
    assert audio_path.exists()
    assert audio_path.read_bytes() == b"audio"

    chunks = result["audio_chunks"]
    assert len(chunks) == 1
    assert Path(chunks[0]).exists()

    manifest_path = Path(result["media_assets_path"])
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest) == 2  # master + chunk
    master_asset = next(item for item in manifest if item["kind"] == "audio_master")
    chunk_asset = next(item for item in manifest if item["kind"] == "audio_chunk")
    assert chunk_asset["parent_asset_id"] == master_asset["asset_id"]
    assert master_asset["duration_ms"] >= chunk_asset["duration_ms"]


def test_process_uploaded_video_missing_source(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        process_uploaded_video(job_id="job", source_path=str(tmp_path / "missing.mp4"))
