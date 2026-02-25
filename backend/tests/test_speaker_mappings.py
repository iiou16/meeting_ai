"""Tests for SpeakerProfile / SpeakerMappings data model and persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meetingai_backend.job_state import (
    SpeakerMappings,
    SpeakerProfile,
    load_speaker_mappings,
    save_speaker_mappings,
)

# ---------------------------------------------------------------------------
# Data model round-trip
# ---------------------------------------------------------------------------


class TestSpeakerProfile:
    def test_to_dict_and_from_dict(self) -> None:
        profile = SpeakerProfile(
            profile_id="abc123",
            name="田中太郎",
            organization="営業部",
        )
        payload = profile.to_dict()
        restored = SpeakerProfile.from_dict(payload)
        assert restored.profile_id == "abc123"
        assert restored.name == "田中太郎"
        assert restored.organization == "営業部"

    def test_from_dict_missing_key_raises(self) -> None:
        with pytest.raises(KeyError):
            SpeakerProfile.from_dict({"profile_id": "x", "name": "x"})


class TestSpeakerMappings:
    def _make_mappings(self) -> SpeakerMappings:
        return SpeakerMappings(
            profiles={
                "p1": SpeakerProfile("p1", "Alice", "Engineering"),
                "p2": SpeakerProfile("p2", "Bob", "Sales"),
            },
            label_to_profile={
                "Speaker A": "p1",
                "Speaker C": "p1",
                "Speaker B": "p2",
            },
        )

    def test_round_trip(self) -> None:
        original = self._make_mappings()
        payload = original.to_dict()
        restored = SpeakerMappings.from_dict(payload)

        assert set(restored.profiles.keys()) == {"p1", "p2"}
        assert restored.profiles["p1"].name == "Alice"
        assert restored.label_to_profile["Speaker A"] == "p1"
        assert restored.label_to_profile["Speaker C"] == "p1"

    def test_resolve_label_mapped(self) -> None:
        m = self._make_mappings()
        profile = m.resolve_label("Speaker A")
        assert profile is not None
        assert profile.name == "Alice"

    def test_resolve_label_merged(self) -> None:
        m = self._make_mappings()
        profile = m.resolve_label("Speaker C")
        assert profile is not None
        assert profile.name == "Alice"

    def test_resolve_label_unmapped(self) -> None:
        m = self._make_mappings()
        assert m.resolve_label("Speaker Z") is None

    def test_from_dict_missing_profiles_raises(self) -> None:
        with pytest.raises(KeyError):
            SpeakerMappings.from_dict({"label_to_profile": {}})

    def test_from_dict_invalid_profiles_type_raises(self) -> None:
        with pytest.raises(TypeError, match="profiles must be a dict"):
            SpeakerMappings.from_dict({"profiles": "bad", "label_to_profile": {}})

    def test_from_dict_invalid_label_map_type_raises(self) -> None:
        with pytest.raises(TypeError, match="label_to_profile must be a dict"):
            SpeakerMappings.from_dict({"profiles": {}, "label_to_profile": "bad"})


# ---------------------------------------------------------------------------
# Persistence (save / load)
# ---------------------------------------------------------------------------


class TestSpeakerMappingsPersistence:
    def test_save_and_load(self, tmp_path: Path) -> None:
        job_dir = tmp_path / "job-1"
        job_dir.mkdir()

        mappings = SpeakerMappings(
            profiles={
                "p1": SpeakerProfile("p1", "田中", "開発"),
            },
            label_to_profile={"Speaker A": "p1"},
        )
        save_speaker_mappings(job_dir, mappings=mappings)

        loaded = load_speaker_mappings(job_dir)
        assert loaded is not None
        assert loaded.profiles["p1"].name == "田中"
        assert loaded.label_to_profile["Speaker A"] == "p1"

    def test_load_returns_none_when_missing(self, tmp_path: Path) -> None:
        job_dir = tmp_path / "job-empty"
        job_dir.mkdir()
        assert load_speaker_mappings(job_dir) is None

    def test_load_raises_on_corrupt_json(self, tmp_path: Path) -> None:
        job_dir = tmp_path / "job-corrupt"
        job_dir.mkdir()
        (job_dir / "speaker_mappings.json").write_text("not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_speaker_mappings(job_dir)

    def test_load_raises_on_non_dict_json(self, tmp_path: Path) -> None:
        job_dir = tmp_path / "job-bad"
        job_dir.mkdir()
        (job_dir / "speaker_mappings.json").write_text('"string"', encoding="utf-8")
        with pytest.raises(ValueError, match="Expected dict"):
            load_speaker_mappings(job_dir)

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        job_dir = tmp_path / "new-job"
        mappings = SpeakerMappings(profiles={}, label_to_profile={})
        save_speaker_mappings(job_dir, mappings=mappings)
        assert (job_dir / "speaker_mappings.json").exists()
