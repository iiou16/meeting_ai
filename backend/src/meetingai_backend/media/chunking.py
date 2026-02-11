"""Utilities to split extracted audio into smaller chunks using FFmpeg."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .assets import MediaAsset

DEFAULT_CHUNK_DURATION_SECONDS = 15 * 60


@dataclass(slots=True, frozen=True)
class AudioChunkSpec:
    """Metadata describing an audio chunk produced during splitting."""

    asset: MediaAsset
    path: Path


def _derive_ffprobe_path(ffmpeg_path: str) -> str:
    """Derive the ffprobe binary path from the ffmpeg binary path.

    If ffmpeg_path is a bare command name (no directory component), return
    "ffprobe" so that it is resolved via PATH.  If ffmpeg_path is an absolute
    or relative path, assume ffprobe lives in the same directory.
    """
    ffmpeg = Path(ffmpeg_path)
    if ffmpeg.parent == Path("."):
        # Bare command name like "ffmpeg" — let the OS resolve via PATH.
        return "ffprobe"
    # Absolute or relative path — assume ffprobe sits next to ffmpeg.
    return str(ffmpeg.parent / "ffprobe")


def _get_duration_seconds(source: Path, *, ffprobe_path: str) -> float:
    """Use ffprobe to determine the total duration of an audio file in seconds."""
    command = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(source),
    ]

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"ffprobe binary was not found at '{ffprobe_path}'. "
            "Ensure FFmpeg is installed and the path is correct."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"ffprobe failed with exit code {exc.returncode}: {exc.stderr}"
        ) from exc

    payload = json.loads(result.stdout)
    duration_str = payload["format"]["duration"]
    duration = float(duration_str)
    if duration <= 0:
        raise ValueError(
            f"ffprobe reported non-positive duration ({duration}) for {source}"
        )
    return duration


def _cut_chunk(
    source: Path,
    *,
    output_path: Path,
    start_seconds: float,
    duration_seconds: float,
    ffmpeg_path: str,
) -> None:
    """Cut a single chunk from the source audio using FFmpeg with stream copy."""
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        str(start_seconds),
        "-t",
        str(duration_seconds),
        "-i",
        str(source),
        "-c:a",
        "copy",
        str(output_path),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"FFmpeg binary was not found at '{ffmpeg_path}'.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"FFmpeg chunk extraction failed with exit code {exc.returncode}: {exc.stderr}"
        ) from exc

    if not output_path.exists():
        raise RuntimeError(
            f"FFmpeg reported success but chunk file was not produced: {output_path}"
        )


def split_audio_into_chunks(
    source: Path,
    *,
    job_id: str,
    chunk_duration_seconds: int = DEFAULT_CHUNK_DURATION_SECONDS,
    parent_asset_id: str | None = None,
    output_dir: Path | None = None,
    ffmpeg_path: str = "ffmpeg",
    sample_rate: int = 16_000,
    channels: int = 1,
) -> list[AudioChunkSpec]:
    """Split an audio file into smaller MP3 chunks using FFmpeg."""
    if chunk_duration_seconds <= 0:
        raise ValueError("chunk_duration_seconds must be greater than zero.")

    if not source.exists():
        raise FileNotFoundError(f"audio file does not exist: {source}")

    destination_root = output_dir or (source.parent / "audio_chunks")
    destination_root.mkdir(parents=True, exist_ok=True)

    ffprobe_path = _derive_ffprobe_path(ffmpeg_path)
    total_duration = _get_duration_seconds(source, ffprobe_path=ffprobe_path)

    assets: list[AudioChunkSpec] = []
    index = 0
    position_seconds = 0.0

    while position_seconds < total_duration:
        remaining = total_duration - position_seconds
        chunk_length = min(float(chunk_duration_seconds), remaining)

        chunk_path = destination_root / f"{source.stem}_chunk_{index:04d}.mp3"
        _cut_chunk(
            source,
            output_path=chunk_path,
            start_seconds=position_seconds,
            duration_seconds=chunk_length,
            ffmpeg_path=ffmpeg_path,
        )

        start_ms = int(round(position_seconds * 1000))
        duration_ms = int(round(chunk_length * 1000))
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
            bit_depth=None,
            parent_asset_id=parent_asset_id,
            extra={},
        )

        assets.append(AudioChunkSpec(asset=asset, path=chunk_path))
        position_seconds += chunk_length
        index += 1

    if not assets:
        raise ValueError("audio file contains no audio data; cannot create chunks.")

    return assets


__all__ = [
    "AudioChunkSpec",
    "DEFAULT_CHUNK_DURATION_SECONDS",
    "split_audio_into_chunks",
]
