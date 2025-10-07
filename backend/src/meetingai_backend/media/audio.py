"""FFmpeg-based audio extraction helpers."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class AudioExtractionError(RuntimeError):
    """Raised when audio extraction fails."""


@dataclass(slots=True)
class AudioExtractionConfig:
    """Parameters controlling audio extraction."""

    ffmpeg_path: str
    sample_rate: int = 16_000
    channels: int = 1
    audio_codec: str = "pcm_s16le"


def extract_audio_to_wav(
    source: Path,
    *,
    output_dir: Path | None = None,
    config: AudioExtractionConfig | None = None,
) -> Path:
    """Extract a mono WAV file from the provided video path."""
    if not source.exists():
        raise FileNotFoundError(f"video file does not exist: {source}")

    destination_dir = output_dir or source.parent
    destination_dir.mkdir(parents=True, exist_ok=True)

    destination = destination_dir / f"{source.stem}.wav"
    extractor_config = config or AudioExtractionConfig(ffmpeg_path="ffmpeg")

    command = [
        extractor_config.ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-acodec",
        extractor_config.audio_codec,
        "-ar",
        str(extractor_config.sample_rate),
        "-ac",
        str(extractor_config.channels),
        str(destination),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise AudioExtractionError(
            "FFmpeg binary was not found. Set MEETINGAI_FFMPEG_PATH or install ffmpeg.",
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise AudioExtractionError(
            f"FFmpeg failed with exit code {exc.returncode}: {exc.stderr}",
        ) from exc

    if not destination.exists():
        raise AudioExtractionError(
            "FFmpeg reported success but no audio file was produced."
        )

    return destination


__all__ = ["AudioExtractionConfig", "AudioExtractionError", "extract_audio_to_wav"]
