"""Persistence helpers for summarization artefacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Sequence

from .models import ActionItem, SummaryItem, SummaryQualityMetrics

_SUMMARY_FILENAME = "summary_items.json"
_ACTION_FILENAME = "action_items.json"
_QUALITY_FILENAME = "summary_quality.json"


def _ensure_job_directory(job_directory: Path) -> Path:
    job_directory.mkdir(parents=True, exist_ok=True)
    return job_directory


def dump_summary_items(
    job_directory: Path, summary_items: Sequence[SummaryItem]
) -> Path:
    """Persist summary sections to disk as JSON."""
    directory = _ensure_job_directory(job_directory)
    path = directory / _SUMMARY_FILENAME
    payload = [item.to_dict() for item in summary_items]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_summary_items(job_directory: Path) -> list[SummaryItem]:
    """Load previously stored summary sections for a job."""
    path = job_directory / _SUMMARY_FILENAME
    if not path.exists():
        return []

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("summary manifest must contain a list")

    items: list[SummaryItem] = []
    for entry in raw:
        if isinstance(entry, dict):
            items.append(SummaryItem.from_dict(entry))
    return items


def dump_action_items(job_directory: Path, action_items: Sequence[ActionItem]) -> Path:
    """Persist action items to disk as JSON."""
    directory = _ensure_job_directory(job_directory)
    path = directory / _ACTION_FILENAME
    payload = [item.to_dict() for item in action_items]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_action_items(job_directory: Path) -> list[ActionItem]:
    """Load stored action items for a job."""
    path = job_directory / _ACTION_FILENAME
    if not path.exists():
        return []

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("action item manifest must contain a list")

    items: list[ActionItem] = []
    for entry in raw:
        if isinstance(entry, dict):
            items.append(ActionItem.from_dict(entry))
    return items


def dump_summary_quality(job_directory: Path, metrics: SummaryQualityMetrics) -> Path:
    """Persist summary quality metrics to disk."""
    directory = _ensure_job_directory(job_directory)
    path = directory / _QUALITY_FILENAME
    payload = metrics.to_dict()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_summary_quality(job_directory: Path) -> SummaryQualityMetrics | None:
    """Load previously stored quality metrics, if available."""
    path = job_directory / _QUALITY_FILENAME
    if not path.exists():
        return None

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("summary quality manifest must contain a dict")

    return SummaryQualityMetrics.from_dict(raw)


__all__ = [
    "dump_summary_items",
    "load_summary_items",
    "dump_action_items",
    "load_action_items",
    "dump_summary_quality",
    "load_summary_quality",
]
