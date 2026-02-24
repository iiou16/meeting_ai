from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from meetingai_backend.media.chunking import AudioChunkSpec, split_audio_into_chunks


def _fake_ffprobe_run(command, check, capture_output, text):
    """Fake subprocess.run that handles both ffprobe and ffmpeg calls."""
    binary = Path(command[0]).name
    if binary == "ffprobe":
        # Return a duration of 2.0 seconds
        output = json.dumps({"format": {"duration": "2.0"}})
        return SimpleNamespace(returncode=0, stdout=output, stderr="")
    elif binary == "ffmpeg":
        # Create the output chunk file
        output_path = Path(command[-1])
        output_path.write_bytes(b"mp3-chunk-data")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    raise ValueError(f"Unexpected binary: {binary}")


def _fake_ffprobe_run_with_duration(duration_seconds: float):
    """Factory that creates a fake subprocess.run with a given duration."""

    def fake_run(command, check, capture_output, text):
        binary = Path(command[0]).name
        if binary == "ffprobe":
            output = json.dumps({"format": {"duration": str(duration_seconds)}})
            return SimpleNamespace(returncode=0, stdout=output, stderr="")
        elif binary == "ffmpeg":
            output_path = Path(command[-1])
            output_path.write_bytes(b"mp3-chunk-data")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise ValueError(f"Unexpected binary: {binary}")

    return fake_run


def test_split_audio_into_chunks_creates_expected_segments(
    monkeypatch, tmp_path
) -> None:
    audio = tmp_path / "input.mp3"
    audio.write_bytes(b"fake-mp3-data")

    monkeypatch.setattr(
        "meetingai_backend.media.chunking.subprocess.run",
        _fake_ffprobe_run_with_duration(2.0),
    )

    specs = split_audio_into_chunks(
        audio,
        job_id="job-1",
        chunk_duration_seconds=1,
        output_dir=tmp_path / "chunks",
        ffmpeg_path="ffmpeg",
    )

    assert len(specs) == 2
    assert all(isinstance(spec, AudioChunkSpec) for spec in specs)

    first_asset = specs[0].asset
    second_asset = specs[1].asset
    assert first_asset.duration_ms == pytest.approx(1000, rel=0.01)
    assert second_asset.duration_ms == pytest.approx(1000, rel=0.01)
    assert first_asset.start_ms == 0
    assert second_asset.start_ms >= first_asset.end_ms
    assert first_asset.sample_rate == 16_000
    assert first_asset.channels == 1
    assert first_asset.bit_depth is None

    for index, spec in enumerate(specs):
        assert spec.path.exists()
        assert spec.asset.order == index
        assert spec.path.suffix == ".mp3"


def test_split_audio_into_chunks_single_chunk(monkeypatch, tmp_path) -> None:
    audio = tmp_path / "short.mp3"
    audio.write_bytes(b"fake-mp3-data")

    monkeypatch.setattr(
        "meetingai_backend.media.chunking.subprocess.run",
        _fake_ffprobe_run_with_duration(1.0),
    )

    specs = split_audio_into_chunks(
        audio, job_id="job-1", chunk_duration_seconds=10, ffmpeg_path="ffmpeg"
    )
    assert len(specs) == 1
    assert specs[0].asset.duration_ms >= 900


def test_split_audio_into_chunks_invalid_duration(tmp_path) -> None:
    audio = tmp_path / "input.mp3"
    audio.write_bytes(b"fake-mp3-data")

    with pytest.raises(ValueError):
        split_audio_into_chunks(audio, job_id="job", chunk_duration_seconds=0)


def test_split_audio_into_chunks_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        split_audio_into_chunks(tmp_path / "missing.mp3", job_id="job")


def test_split_audio_into_chunks_zero_duration(monkeypatch, tmp_path) -> None:
    audio = tmp_path / "empty.mp3"
    audio.write_bytes(b"fake-mp3-data")

    def fake_run(command, check, capture_output, text):
        binary = Path(command[0]).name
        if binary == "ffprobe":
            output = json.dumps({"format": {"duration": "0.0"}})
            return SimpleNamespace(returncode=0, stdout=output, stderr="")
        raise ValueError(f"Unexpected binary: {binary}")

    monkeypatch.setattr(
        "meetingai_backend.media.chunking.subprocess.run",
        fake_run,
    )

    with pytest.raises(ValueError, match="non-positive duration"):
        split_audio_into_chunks(audio, job_id="job", ffmpeg_path="ffmpeg")
