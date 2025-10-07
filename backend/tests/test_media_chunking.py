from __future__ import annotations

import wave
from pathlib import Path

import pytest

from meetingai_backend.media.chunking import AudioChunkSpec, split_wav_into_chunks


def _create_silent_wav(
    path: Path,
    *,
    duration_seconds: int,
    sample_rate: int = 16_000,
    channels: int = 1,
) -> None:
    total_frames = duration_seconds * sample_rate
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * total_frames * channels)


def test_split_wav_into_chunks_creates_expected_segments(tmp_path) -> None:
    audio = tmp_path / "input.wav"
    _create_silent_wav(audio, duration_seconds=2, sample_rate=16_000, channels=1)

    specs = split_wav_into_chunks(
        audio,
        job_id="job-1",
        chunk_duration_seconds=1,
        output_dir=tmp_path / "chunks",
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
    assert first_asset.bit_depth == 16

    for index, spec in enumerate(specs):
        assert spec.path.exists()
        assert spec.asset.order == index
        with wave.open(str(spec.path), "rb") as chunk:
            assert chunk.getnchannels() == 1
            assert chunk.getframerate() == 16_000


def test_split_wav_into_chunks_single_chunk(tmp_path) -> None:
    audio = tmp_path / "short.wav"
    _create_silent_wav(audio, duration_seconds=1)

    specs = split_wav_into_chunks(audio, job_id="job-1", chunk_duration_seconds=10)
    assert len(specs) == 1
    assert specs[0].asset.duration_ms >= 900


def test_split_wav_into_chunks_invalid_duration(tmp_path) -> None:
    audio = tmp_path / "input.wav"
    _create_silent_wav(audio, duration_seconds=1)

    with pytest.raises(ValueError):
        split_wav_into_chunks(audio, job_id="job", chunk_duration_seconds=0)


def test_split_wav_into_chunks_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        split_wav_into_chunks(tmp_path / "missing.wav", job_id="job")


def test_split_wav_into_chunks_empty_audio(tmp_path) -> None:
    audio = tmp_path / "empty.wav"
    with wave.open(str(audio), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16_000)
        wav_file.writeframes(b"")

    with pytest.raises(ValueError, match="contains no frames"):
        split_wav_into_chunks(audio, job_id="job")
