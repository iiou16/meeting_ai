from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from meetingai_backend.media.audio import (
    AudioExtractionConfig,
    AudioExtractionError,
    extract_audio,
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
        Path(command[-1]).write_bytes(b"mp3-data")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("meetingai_backend.media.audio.subprocess.run", fake_run)

    result = extract_audio(
        video, config=AudioExtractionConfig(ffmpeg_path="ffmpeg-binary")
    )

    assert issued_commands, "expected ffmpeg to be invoked"
    command = issued_commands[0]
    assert command[0] == "ffmpeg-binary"
    assert "-b:a" in command
    assert "64k" in command
    assert "libmp3lame" in command
    assert result.exists()
    assert result.read_bytes() == b"mp3-data"


def test_extract_audio_missing_ffmpeg(monkeypatch, tmp_path) -> None:
    video = _create_video_file(tmp_path)

    def fake_run(command, check, capture_output, text):
        raise FileNotFoundError("ffmpeg not found")

    monkeypatch.setattr("meetingai_backend.media.audio.subprocess.run", fake_run)

    with pytest.raises(AudioExtractionError, match="FFmpeg binary was not found"):
        extract_audio(video)


def test_extract_audio_output_never_collides_with_input(monkeypatch, tmp_path) -> None:
    """出力ファイル名が入力ファイルと衝突しないことを確認する。"""
    mp3_input = tmp_path / "recording.mp3"
    mp3_input.write_bytes(b"fake-mp3-data")

    issued_commands: list[list[str]] = []

    def fake_run(command, check, capture_output, text):
        issued_commands.append(command)
        Path(command[-1]).write_bytes(b"mp3-data")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("meetingai_backend.media.audio.subprocess.run", fake_run)

    result = extract_audio(mp3_input)

    assert result != mp3_input, "出力パスが入力パスと同一になっている"
    assert result.name == "recording_audio.mp3"
    assert result.exists()


def test_extract_audio_mp4_output_name(monkeypatch, tmp_path) -> None:
    """mp4入力でも出力ファイル名に _audio が付くことを確認する。"""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake-video-data")

    def fake_run(command, check, capture_output, text):
        Path(command[-1]).write_bytes(b"mp3-data")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("meetingai_backend.media.audio.subprocess.run", fake_run)

    result = extract_audio(video)

    assert result.name == "clip_audio.mp3"


def test_extract_audio_failure(monkeypatch, tmp_path) -> None:
    video = _create_video_file(tmp_path)

    def fake_run(command, check, capture_output, text):
        raise subprocess.CalledProcessError(
            returncode=1, cmd=command, stderr="bad input"
        )

    monkeypatch.setattr("meetingai_backend.media.audio.subprocess.run", fake_run)

    with pytest.raises(AudioExtractionError, match="FFmpeg failed"):
        extract_audio(video)
