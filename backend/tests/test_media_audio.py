from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from meetingai_backend.media.audio import (
    AudioExtractionConfig,
    AudioExtractionError,
    extract_audio_to_wav,
)


def _create_video_file(tmp_path: Path) -> Path:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake-video-data")
    return video


def test_extract_audio_invokes_ffmpeg(monkeypatch, tmp_path) -> None:
    video = _create_video_file(tmp_path)
    issued_commands: list[list[str]] = []

    def fake_run(command, check, capture_output, text):
        issued_commands.append(command)
        Path(command[-1]).write_bytes(b"wav-data")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("meetingai_backend.media.audio.subprocess.run", fake_run)

    result = extract_audio_to_wav(
        video, config=AudioExtractionConfig(ffmpeg_path="ffmpeg-binary")
    )

    assert issued_commands, "expected ffmpeg to be invoked"
    command = issued_commands[0]
    assert command[0] == "ffmpeg-binary"
    assert result.exists()
    assert result.read_bytes() == b"wav-data"


def test_extract_audio_missing_ffmpeg(monkeypatch, tmp_path) -> None:
    video = _create_video_file(tmp_path)

    def fake_run(command, check, capture_output, text):
        raise FileNotFoundError("ffmpeg not found")

    monkeypatch.setattr("meetingai_backend.media.audio.subprocess.run", fake_run)

    with pytest.raises(AudioExtractionError, match="FFmpeg binary was not found"):
        extract_audio_to_wav(video)


def test_extract_audio_failure(monkeypatch, tmp_path) -> None:
    video = _create_video_file(tmp_path)

    def fake_run(command, check, capture_output, text):
        raise subprocess.CalledProcessError(
            returncode=1, cmd=command, stderr="bad input"
        )

    monkeypatch.setattr("meetingai_backend.media.audio.subprocess.run", fake_run)

    with pytest.raises(AudioExtractionError, match="FFmpeg failed"):
        extract_audio_to_wav(video)
