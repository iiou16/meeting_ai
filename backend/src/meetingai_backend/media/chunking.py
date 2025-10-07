"""Utilities to split extracted audio into smaller chunks."""

from __future__ import annotations

import contextlib
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .assets import MediaAsset

DEFAULT_CHUNK_DURATION_SECONDS = 15 * 60


@dataclass(slots=True, frozen=True)
class AudioChunkSpec:
    """Metadata describing an audio chunk produced during splitting."""

    asset: MediaAsset
    path: Path


def _iter_chunks(
    wav_file: wave.Wave_read, *, frames_per_chunk: int
) -> Iterator[tuple[int, bytes, int]]:
    """Yield sequential chunks of audio data from the wave file."""
    index = 0
    while True:
        frames = wav_file.readframes(frames_per_chunk)
        if not frames:
            break
        frames_read = len(frames) // (wav_file.getsampwidth() * wav_file.getnchannels())
        yield index, frames, frames_read
        index += 1


def split_wav_into_chunks(
    source: Path,
    *,
    job_id: str,
    chunk_duration_seconds: int = DEFAULT_CHUNK_DURATION_SECONDS,
    parent_asset_id: str | None = None,
    output_dir: Path | None = None,
) -> list[AudioChunkSpec]:
    """Split a WAV file into smaller chunks and capture metadata for each piece."""
    if chunk_duration_seconds <= 0:
        raise ValueError("chunk_duration_seconds must be greater than zero.")

    if not source.exists():
        raise FileNotFoundError(f"audio file does not exist: {source}")

    destination_root = output_dir or (source.parent / "audio_chunks")
    destination_root.mkdir(parents=True, exist_ok=True)

    with contextlib.closing(wave.open(str(source), "rb")) as wav_reader:
        channels = wav_reader.getnchannels()
        sample_width = wav_reader.getsampwidth()
        sample_rate = wav_reader.getframerate()
        total_frames = wav_reader.getnframes()

        if total_frames == 0:
            raise ValueError("audio file contains no frames; cannot create chunks.")

        frames_per_chunk = chunk_duration_seconds * sample_rate
        if frames_per_chunk <= 0:
            raise ValueError("chunk duration results in zero frames per chunk.")

        assets: list[AudioChunkSpec] = []
        position_frames = 0

        for index, frame_data, frames_read in _iter_chunks(
            wav_reader, frames_per_chunk=frames_per_chunk
        ):
            chunk_path = destination_root / f"{source.stem}_chunk_{index:04d}.wav"
            with contextlib.closing(wave.open(str(chunk_path), "wb")) as chunk_writer:
                chunk_writer.setnchannels(channels)
                chunk_writer.setsampwidth(sample_width)
                chunk_writer.setframerate(sample_rate)
                chunk_writer.writeframes(frame_data)

            duration_ms = int(round(frames_read / sample_rate * 1000))
            start_ms = int(round(position_frames / sample_rate * 1000))
            end_ms = start_ms + duration_ms

            asset = MediaAsset(
                asset_id=MediaAsset.create_id(),
                job_id=job_id,
                kind="audio_chunk",
                path=chunk_path.resolve(),
                order=index,
                duration_ms=duration_ms,
                start_ms=start_ms,
                end_ms=end_ms,
                sample_rate=sample_rate,
                channels=channels,
                bit_depth=sample_width * 8,
                parent_asset_id=parent_asset_id,
                extra={"frames": frames_read},
            )

            assets.append(AudioChunkSpec(asset=asset, path=chunk_path))
            position_frames += frames_read

    return assets


__all__ = ["AudioChunkSpec", "DEFAULT_CHUNK_DURATION_SECONDS", "split_wav_into_chunks"]
