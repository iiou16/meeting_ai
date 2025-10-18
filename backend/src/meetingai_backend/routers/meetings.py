"""Endpoints for retrieving meeting artefacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..settings import Settings, get_settings
from ..summarization import (
    ActionItem,
    SummaryItem,
    load_action_items,
    load_summary_items,
    load_summary_quality,
)
from ..transcription.segments import TranscriptSegment, load_transcript_segments

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


class TranscriptSegmentResponse(BaseModel):
    segment_id: str
    job_id: str
    order: int
    start_ms: int
    end_ms: int
    text: str
    language: str | None = None
    speaker_label: str | None = None

    @classmethod
    def from_segment(cls, segment: TranscriptSegment) -> "TranscriptSegmentResponse":
        return cls(
            segment_id=segment.segment_id,
            job_id=segment.job_id,
            order=segment.order,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            text=segment.text,
            language=segment.language,
            speaker_label=segment.speaker_label,
        )


class SummaryItemResponse(BaseModel):
    summary_id: str
    job_id: str
    order: int
    segment_start_ms: int
    segment_end_ms: int
    summary_text: str
    heading: str | None = None
    priority: str | None = None
    highlights: list[str] = Field(default_factory=list)

    @classmethod
    def from_item(cls, item: SummaryItem) -> "SummaryItemResponse":
        return cls(
            summary_id=item.summary_id,
            job_id=item.job_id,
            order=item.order,
            segment_start_ms=item.segment_start_ms,
            segment_end_ms=item.segment_end_ms,
            summary_text=item.summary_text,
            heading=item.heading,
            priority=item.priority,
            highlights=list(item.highlights),
        )


class ActionItemResponse(BaseModel):
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
    def from_item(cls, item: ActionItem) -> "ActionItemResponse":
        return cls(
            action_id=item.action_id,
            job_id=item.job_id,
            order=item.order,
            description=item.description,
            owner=item.owner,
            due_date=item.due_date,
            segment_start_ms=item.segment_start_ms,
            segment_end_ms=item.segment_end_ms,
            priority=item.priority,
        )


class MeetingResponse(BaseModel):
    job_id: str
    summary_items: list[SummaryItemResponse]
    action_items: list[ActionItemResponse]
    segments: list[TranscriptSegmentResponse]
    quality_metrics: dict[str, Any] | None = None


def _resolve_job_directory(settings: Settings, job_id: str) -> Path:
    job_directory = settings.upload_root / job_id
    if not job_directory.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "meeting not found")
    return job_directory


@router.get("/{job_id}", response_model=MeetingResponse)
def get_meeting(
    job_id: str, settings: Settings = Depends(get_settings)
) -> MeetingResponse:
    """Return full meeting artefacts for the given job."""
    job_directory = _resolve_job_directory(settings, job_id)

    segments = load_transcript_segments(job_directory)
    summary_items = load_summary_items(job_directory)
    action_items = load_action_items(job_directory)
    quality = load_summary_quality(job_directory)

    return MeetingResponse(
        job_id=job_id,
        summary_items=[SummaryItemResponse.from_item(item) for item in summary_items],
        action_items=[ActionItemResponse.from_item(item) for item in action_items],
        segments=[TranscriptSegmentResponse.from_segment(seg) for seg in segments],
        quality_metrics=quality.to_dict() if quality else None,
    )


__all__ = ["router"]
