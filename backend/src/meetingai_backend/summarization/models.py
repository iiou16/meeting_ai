"""Dataclasses and helpers for meeting summaries."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


def _generate_id() -> str:
    return uuid.uuid4().hex


@dataclass(slots=True)
class SummaryItem:
    """Represents a summarized section of the meeting."""

    summary_id: str
    job_id: str
    order: int
    segment_start_ms: int
    segment_end_ms: int
    summary_text: str
    heading: str | None = None
    priority: str | None = None
    highlights: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        job_id: str,
        order: int,
        segment_start_ms: int,
        segment_end_ms: int,
        summary_text: str,
        heading: str | None = None,
        priority: str | None = None,
        highlights: Sequence[str] | None = None,
    ) -> "SummaryItem":
        return cls(
            summary_id=_generate_id(),
            job_id=job_id,
            order=order,
            segment_start_ms=int(segment_start_ms),
            segment_end_ms=int(segment_end_ms),
            summary_text=summary_text,
            heading=heading,
            priority=priority,
            highlights=list(highlights or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary_id": self.summary_id,
            "job_id": self.job_id,
            "order": self.order,
            "segment_start_ms": self.segment_start_ms,
            "segment_end_ms": self.segment_end_ms,
            "summary_text": self.summary_text,
            "heading": self.heading,
            "priority": self.priority,
            "highlights": list(self.highlights),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SummaryItem":
        return cls(
            summary_id=str(payload["summary_id"]),
            job_id=str(payload["job_id"]),
            order=int(payload["order"]),
            segment_start_ms=int(payload["segment_start_ms"]),
            segment_end_ms=int(payload["segment_end_ms"]),
            summary_text=str(payload["summary_text"]),
            heading=str(payload["heading"]) if payload.get("heading") else None,
            priority=str(payload["priority"]) if payload.get("priority") else None,
            highlights=list(payload.get("highlights") or []),
        )


@dataclass(slots=True)
class ActionItem:
    """Represents an actionable follow-up extracted from the meeting."""

    action_id: str
    job_id: str
    order: int
    description: str
    owner: str | None = None
    due_date: str | None = None
    segment_start_ms: int | None = None
    segment_end_ms: int | None = None
    priority: str | None = None

    @classmethod
    def create(
        cls,
        *,
        job_id: str,
        order: int,
        description: str,
        owner: str | None = None,
        due_date: str | None = None,
        segment_start_ms: int | None = None,
        segment_end_ms: int | None = None,
        priority: str | None = None,
    ) -> "ActionItem":
        return cls(
            action_id=_generate_id(),
            job_id=job_id,
            order=order,
            description=description,
            owner=owner,
            due_date=due_date,
            segment_start_ms=(
                int(segment_start_ms) if segment_start_ms is not None else None
            ),
            segment_end_ms=int(segment_end_ms) if segment_end_ms is not None else None,
            priority=priority,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "job_id": self.job_id,
            "order": self.order,
            "description": self.description,
            "owner": self.owner,
            "due_date": self.due_date,
            "segment_start_ms": self.segment_start_ms,
            "segment_end_ms": self.segment_end_ms,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ActionItem":
        segment_start = payload.get("segment_start_ms")
        segment_end = payload.get("segment_end_ms")
        return cls(
            action_id=str(payload["action_id"]),
            job_id=str(payload["job_id"]),
            order=int(payload["order"]),
            description=str(payload["description"]),
            owner=str(payload["owner"]) if payload.get("owner") else None,
            due_date=str(payload["due_date"]) if payload.get("due_date") else None,
            segment_start_ms=int(segment_start) if segment_start is not None else None,
            segment_end_ms=int(segment_end) if segment_end is not None else None,
            priority=str(payload["priority"]) if payload.get("priority") else None,
        )


@dataclass(slots=True)
class SummaryQualityMetrics:
    """Derived metrics used to evaluate summary coverage and density."""

    coverage_ratio: float
    referenced_segments_ratio: float
    average_summary_word_count: float
    action_item_count: int
    llm_confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage_ratio": self.coverage_ratio,
            "referenced_segments_ratio": self.referenced_segments_ratio,
            "average_summary_word_count": self.average_summary_word_count,
            "action_item_count": self.action_item_count,
            "llm_confidence": self.llm_confidence,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SummaryQualityMetrics":
        return cls(
            coverage_ratio=float(payload.get("coverage_ratio", 0.0)),
            referenced_segments_ratio=float(
                payload.get("referenced_segments_ratio", 0.0)
            ),
            average_summary_word_count=float(
                payload.get("average_summary_word_count", 0.0)
            ),
            action_item_count=int(payload.get("action_item_count", 0)),
            llm_confidence=(
                float(payload["llm_confidence"])
                if payload.get("llm_confidence") is not None
                else None
            ),
        )


@dataclass(slots=True)
class SummaryBundle:
    """Container for summary + action items and derived metrics."""

    summary_items: list[SummaryItem]
    action_items: list[ActionItem]
    quality: SummaryQualityMetrics
    model_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary_items": [item.to_dict() for item in self.summary_items],
            "action_items": [item.to_dict() for item in self.action_items],
            "quality": self.quality.to_dict(),
            "model_metadata": dict(self.model_metadata),
        }


__all__ = ["ActionItem", "SummaryBundle", "SummaryItem", "SummaryQualityMetrics"]
