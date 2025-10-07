"""Domain models and persistence helpers for media assets."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence


@dataclass(slots=True)
class MediaAsset:
    """Represents a stored media artifact associated with a processing job."""

    asset_id: str
    job_id: str
    kind: str
    path: Path
    order: int
    duration_ms: int
    start_ms: int
    end_ms: int
    sample_rate: int | None = None
    channels: int | None = None
    bit_depth: int | None = None
    parent_asset_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the media asset into a JSON-serialisable dictionary."""
        return {
            "asset_id": self.asset_id,
            "job_id": self.job_id,
            "kind": self.kind,
            "path": str(self.path),
            "order": self.order,
            "duration_ms": self.duration_ms,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bit_depth": self.bit_depth,
            "parent_asset_id": self.parent_asset_id,
            "extra": self.extra,
        }

    @classmethod
    def create_id(cls) -> str:
        """Generate a unique identifier for a media asset."""
        return uuid.uuid4().hex

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MediaAsset":
        """Reconstruct a media asset from a dictionary."""
        return cls(
            asset_id=payload["asset_id"],
            job_id=payload["job_id"],
            kind=payload["kind"],
            path=Path(payload["path"]),
            order=payload["order"],
            duration_ms=payload["duration_ms"],
            start_ms=payload["start_ms"],
            end_ms=payload["end_ms"],
            sample_rate=payload.get("sample_rate"),
            channels=payload.get("channels"),
            bit_depth=payload.get("bit_depth"),
            parent_asset_id=payload.get("parent_asset_id"),
            extra=payload.get("extra") or {},
        )


def dump_media_assets(job_directory: Path, assets: Sequence[MediaAsset]) -> Path:
    """Persist the provided media asset collection to a JSON file."""
    job_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = job_directory / "media_assets.json"
    content = [asset.to_dict() for asset in assets]
    manifest_path.write_text(json.dumps(content, indent=2), encoding="utf-8")
    return manifest_path


def load_media_assets(job_directory: Path) -> list[MediaAsset]:
    """Load media assets previously stored for the given job directory."""
    manifest_path = job_directory / "media_assets.json"
    if not manifest_path.exists():
        return []

    raw_assets = json.loads(manifest_path.read_text(encoding="utf-8"))
    return [MediaAsset.from_dict(item) for item in raw_assets]


def merge_media_assets(
    existing: Iterable[MediaAsset],
    new_assets: Iterable[MediaAsset],
) -> list[MediaAsset]:
    """Merge two media asset iterables, replacing duplicates by asset_id."""
    merged: dict[str, MediaAsset] = {asset.asset_id: asset for asset in existing}
    for asset in new_assets:
        merged[asset.asset_id] = asset
    return list(merged.values())


__all__ = ["MediaAsset", "dump_media_assets", "load_media_assets", "merge_media_assets"]
