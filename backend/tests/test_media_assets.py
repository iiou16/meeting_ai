"""Tests for meetingai_backend.media.assets module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meetingai_backend.media.assets import (
    MediaAsset,
    dump_media_assets,
    load_media_assets,
    merge_media_assets,
)


def _make_asset(
    *,
    asset_id: str = "a1",
    job_id: str = "job-1",
    kind: str = "audio_chunk",
    path: Path = Path("/tmp/chunk.mp3"),
    order: int = 0,
    duration_ms: int = 60_000,
    start_ms: int = 0,
    end_ms: int = 60_000,
    sample_rate: int | None = 16_000,
    channels: int | None = 1,
    bit_depth: int | None = 16,
    parent_asset_id: str | None = None,
    extra: dict | None = None,
) -> MediaAsset:
    return MediaAsset(
        asset_id=asset_id,
        job_id=job_id,
        kind=kind,
        path=path,
        order=order,
        duration_ms=duration_ms,
        start_ms=start_ms,
        end_ms=end_ms,
        sample_rate=sample_rate,
        channels=channels,
        bit_depth=bit_depth,
        parent_asset_id=parent_asset_id,
        extra=extra or {},
    )


# ---------- TestMediaAssetToDict ----------


class TestMediaAssetToDict:
    def test_to_dict_contains_all_fields(self) -> None:
        asset = _make_asset()
        d = asset.to_dict()
        assert d["asset_id"] == "a1"
        assert d["job_id"] == "job-1"
        assert d["kind"] == "audio_chunk"
        assert d["path"] == "/tmp/chunk.mp3"
        assert d["order"] == 0
        assert d["duration_ms"] == 60_000
        assert d["start_ms"] == 0
        assert d["end_ms"] == 60_000
        assert d["sample_rate"] == 16_000
        assert d["channels"] == 1
        assert d["bit_depth"] == 16
        assert d["parent_asset_id"] is None
        assert d["extra"] == {}

    def test_to_dict_path_serialized_as_string(self) -> None:
        asset = _make_asset(path=Path("/data/audio/file.wav"))
        d = asset.to_dict()
        assert isinstance(d["path"], str)
        assert d["path"] == "/data/audio/file.wav"

    def test_to_dict_optional_fields_none(self) -> None:
        asset = _make_asset(
            sample_rate=None, channels=None, bit_depth=None, parent_asset_id=None
        )
        d = asset.to_dict()
        assert d["sample_rate"] is None
        assert d["channels"] is None
        assert d["bit_depth"] is None
        assert d["parent_asset_id"] is None


# ---------- TestMediaAssetFromDict ----------


class TestMediaAssetFromDict:
    def test_roundtrip_to_dict_from_dict(self) -> None:
        original = _make_asset(extra={"codec": "mp3"})
        restored = MediaAsset.from_dict(original.to_dict())
        assert restored.asset_id == original.asset_id
        assert restored.job_id == original.job_id
        assert restored.kind == original.kind
        assert restored.path == original.path
        assert restored.order == original.order
        assert restored.duration_ms == original.duration_ms
        assert restored.start_ms == original.start_ms
        assert restored.end_ms == original.end_ms
        assert restored.sample_rate == original.sample_rate
        assert restored.channels == original.channels
        assert restored.bit_depth == original.bit_depth
        assert restored.parent_asset_id == original.parent_asset_id
        assert restored.extra == original.extra

    def test_from_dict_path_becomes_path_object(self) -> None:
        d = _make_asset().to_dict()
        assert isinstance(d["path"], str)
        restored = MediaAsset.from_dict(d)
        assert isinstance(restored.path, Path)

    def test_from_dict_missing_required_field_raises(self) -> None:
        d = _make_asset().to_dict()
        del d["asset_id"]
        with pytest.raises(KeyError):
            MediaAsset.from_dict(d)

    def test_from_dict_extra_none_normalized_to_empty_dict(self) -> None:
        d = _make_asset().to_dict()
        d["extra"] = None
        restored = MediaAsset.from_dict(d)
        assert restored.extra == {}

    def test_from_dict_extra_missing_raises(self) -> None:
        d = _make_asset().to_dict()
        del d["extra"]
        with pytest.raises(KeyError):
            MediaAsset.from_dict(d)


# ---------- TestMediaAssetCreateId ----------


class TestMediaAssetCreateId:
    def test_create_id_returns_hex_string(self) -> None:
        aid = MediaAsset.create_id()
        assert isinstance(aid, str)
        assert len(aid) == 32
        int(aid, 16)  # raises ValueError if not hex

    def test_create_id_unique(self) -> None:
        ids = {MediaAsset.create_id() for _ in range(100)}
        assert len(ids) == 100


# ---------- TestDumpAndLoadMediaAssets ----------


class TestDumpAndLoadMediaAssets:
    def test_dump_creates_json_file_with_correct_content(self, tmp_path: Path) -> None:
        asset = _make_asset(asset_id="a1", path=tmp_path / "chunk.mp3")
        result_path = dump_media_assets(tmp_path, [asset])
        assert result_path == tmp_path / "media_assets.json"
        assert result_path.exists()
        content = json.loads(result_path.read_text(encoding="utf-8"))
        assert len(content) == 1
        assert content[0]["asset_id"] == "a1"
        assert isinstance(content[0]["path"], str)

    def test_dump_creates_parent_directories(self, tmp_path: Path) -> None:
        deep_dir = tmp_path / "a" / "b" / "c"
        asset = _make_asset(path=deep_dir / "chunk.mp3")
        result_path = dump_media_assets(deep_dir, [asset])
        assert result_path.exists()

    def test_dump_and_load_roundtrip(self, tmp_path: Path) -> None:
        assets = [
            _make_asset(asset_id="a1", order=0, path=tmp_path / "c0.mp3"),
            _make_asset(asset_id="a2", order=1, path=tmp_path / "c1.mp3"),
        ]
        dump_media_assets(tmp_path, assets)
        loaded = load_media_assets(tmp_path)
        assert len(loaded) == 2
        assert loaded[0].asset_id == "a1"
        assert loaded[1].asset_id == "a2"
        assert isinstance(loaded[0].path, Path)

    def test_load_raises_when_file_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_media_assets(tmp_path)

    def test_load_invalid_json_propagates_error(self, tmp_path: Path) -> None:
        manifest = tmp_path / "media_assets.json"
        manifest.write_text("{invalid json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_media_assets(tmp_path)


# ---------- TestMergeMediaAssets ----------


class TestMergeMediaAssets:
    def test_merge_replaces_duplicate_by_asset_id(self) -> None:
        old = _make_asset(asset_id="a1", kind="original")
        new = _make_asset(asset_id="a1", kind="updated")
        merged = merge_media_assets([old], [new])
        assert len(merged) == 1
        assert merged[0].kind == "updated"

    def test_merge_preserves_insertion_order(self) -> None:
        existing = [
            _make_asset(asset_id="a1", order=0),
            _make_asset(asset_id="a2", order=1),
        ]
        new_assets = [
            _make_asset(asset_id="a3", order=2),
            _make_asset(asset_id="a1", order=0, kind="replaced"),
        ]
        merged = merge_media_assets(existing, new_assets)
        ids = [a.asset_id for a in merged]
        assert ids == ["a1", "a2", "a3"]
        assert merged[0].kind == "replaced"

    def test_merge_duplicate_ids_in_new_assets_last_wins(self) -> None:
        new_assets = [
            _make_asset(asset_id="a1", kind="first"),
            _make_asset(asset_id="a1", kind="last"),
        ]
        merged = merge_media_assets([], new_assets)
        assert len(merged) == 1
        assert merged[0].kind == "last"


# ---------- Additional edge cases ----------


class TestDumpEmptyAssets:
    def test_dump_empty_list_creates_valid_json(self, tmp_path: Path) -> None:
        result_path = dump_media_assets(tmp_path, [])
        assert result_path.exists()
        content = json.loads(result_path.read_text(encoding="utf-8"))
        assert content == []


class TestFromDictOptionalFieldsMissing:
    @pytest.mark.parametrize(
        "field_name", ["sample_rate", "channels", "bit_depth", "parent_asset_id"]
    )
    def test_from_dict_optional_fields_missing_raises(self, field_name: str) -> None:
        d = _make_asset().to_dict()
        del d[field_name]
        with pytest.raises(KeyError):
            MediaAsset.from_dict(d)


class TestLoadNonArrayJson:
    def test_load_non_array_json_raises(self, tmp_path: Path) -> None:
        manifest = tmp_path / "media_assets.json"
        manifest.write_text('{"key": "value"}', encoding="utf-8")
        with pytest.raises(TypeError):
            load_media_assets(tmp_path)
