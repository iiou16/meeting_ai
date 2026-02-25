"""Tests for get_creation_time in media/chunking.py."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from meetingai_backend.media.chunking import get_creation_time

_JST = timezone(timedelta(hours=9))


def _make_ffprobe_result(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["ffprobe"], returncode=0, stdout=stdout, stderr=""
    )


class TestGetCreationTime:
    """Tests for get_creation_time()."""

    def test_extracts_from_format_tags(self, tmp_path: Path) -> None:
        source = tmp_path / "video.mp4"
        source.write_bytes(b"\x00")

        payload = {
            "format": {"tags": {"creation_time": "2025-01-15T10:30:00.000000Z"}},
        }
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_ffprobe_result(json.dumps(payload))
            result = get_creation_time(source, ffprobe_path="ffprobe")

        assert result is not None
        expected = datetime(2025, 1, 15, 19, 30, 0, tzinfo=_JST)
        assert result == expected

    def test_extracts_from_stream_tags_when_format_absent(self, tmp_path: Path) -> None:
        source = tmp_path / "video.mp4"
        source.write_bytes(b"\x00")

        payload = {
            "format": {},
            "streams": [{"tags": {"creation_time": "2025-06-01T12:00:00.000000Z"}}],
        }
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_ffprobe_result(json.dumps(payload))
            result = get_creation_time(source, ffprobe_path="ffprobe")

        assert result is not None
        expected = datetime(2025, 6, 1, 21, 0, 0, tzinfo=_JST)
        assert result == expected

    def test_returns_none_when_no_tags(self, tmp_path: Path) -> None:
        source = tmp_path / "video.mp4"
        source.write_bytes(b"\x00")

        payload = {"format": {}, "streams": []}
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_ffprobe_result(json.dumps(payload))
            result = get_creation_time(source, ffprobe_path="ffprobe")

        assert result is None

    def test_raises_on_ffprobe_not_found(self, tmp_path: Path) -> None:
        source = tmp_path / "video.mp4"
        source.write_bytes(b"\x00")

        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match="ffprobe binary was not found"):
                get_creation_time(source, ffprobe_path="/bad/ffprobe")

    def test_raises_on_ffprobe_failure(self, tmp_path: Path) -> None:
        source = tmp_path / "video.mp4"
        source.write_bytes(b"\x00")

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "ffprobe", stderr="error"),
        ):
            with pytest.raises(RuntimeError, match="ffprobe failed"):
                get_creation_time(source, ffprobe_path="ffprobe")

    def test_naive_datetime_treated_as_jst(self, tmp_path: Path) -> None:
        source = tmp_path / "video.mp4"
        source.write_bytes(b"\x00")

        payload = {
            "format": {"tags": {"creation_time": "2025-03-20T14:00:00"}},
        }
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_ffprobe_result(json.dumps(payload))
            result = get_creation_time(source, ffprobe_path="ffprobe")

        assert result is not None
        assert result.tzinfo == _JST
        assert result == datetime(2025, 3, 20, 14, 0, 0, tzinfo=_JST)

    def test_utc_offset_converted_to_jst(self, tmp_path: Path) -> None:
        source = tmp_path / "video.mp4"
        source.write_bytes(b"\x00")

        payload = {
            "format": {
                "tags": {"creation_time": "2025-01-15T10:30:00+00:00"},
            },
        }
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_ffprobe_result(json.dumps(payload))
            result = get_creation_time(source, ffprobe_path="ffprobe")

        assert result is not None
        expected = datetime(2025, 1, 15, 19, 30, 0, tzinfo=_JST)
        assert result == expected
