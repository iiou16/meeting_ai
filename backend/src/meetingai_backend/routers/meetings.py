"""Endpoints for retrieving meeting artefacts."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field, field_validator

from ..job_state import (
    SpeakerMappings,
    SpeakerProfile,
    load_speaker_mappings,
    save_speaker_mappings,
)
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


# --- Speaker mappings request / response models ---


class SpeakerProfileInput(BaseModel):
    profile_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    organization: str = ""


class SpeakerMappingsInput(BaseModel):
    profiles: dict[str, SpeakerProfileInput]
    label_to_profile: dict[str, str]

    @field_validator("label_to_profile")
    @classmethod
    def all_profile_ids_must_exist(cls, v: dict[str, str], info: Any) -> dict[str, str]:
        # When earlier field validation fails, profiles may not be in info.data
        if "profiles" not in info.data:
            return v
        profiles = info.data["profiles"]
        for label, profile_id in v.items():
            if profile_id not in profiles:
                raise ValueError(
                    f"label_to_profile[{label!r}] references unknown "
                    f"profile_id {profile_id!r}"
                )
        return v


class SpeakerProfileResponse(BaseModel):
    profile_id: str
    name: str
    organization: str


class SpeakerMappingsResponse(BaseModel):
    profiles: dict[str, SpeakerProfileResponse]
    label_to_profile: dict[str, str]


class MeetingResponse(BaseModel):
    job_id: str
    summary_items: list[SummaryItemResponse]
    action_items: list[ActionItemResponse]
    segments: list[TranscriptSegmentResponse]
    quality_metrics: dict[str, Any] | None = None
    speaker_mappings: SpeakerMappingsResponse | None = None


def _resolve_job_directory(settings: Settings, job_id: str) -> Path:
    job_directory = settings.upload_root / job_id
    if not job_directory.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "meeting not found")
    return job_directory


def _mappings_to_response(
    mappings: SpeakerMappings | None,
) -> SpeakerMappingsResponse | None:
    if mappings is None:
        return None
    return SpeakerMappingsResponse(
        profiles={
            pid: SpeakerProfileResponse(
                profile_id=p.profile_id,
                name=p.name,
                organization=p.organization,
            )
            for pid, p in mappings.profiles.items()
        },
        label_to_profile=dict(mappings.label_to_profile),
    )


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
    mappings = load_speaker_mappings(job_directory)

    return MeetingResponse(
        job_id=job_id,
        summary_items=[SummaryItemResponse.from_item(item) for item in summary_items],
        action_items=[ActionItemResponse.from_item(item) for item in action_items],
        segments=[TranscriptSegmentResponse.from_segment(seg) for seg in segments],
        quality_metrics=quality.to_dict() if quality else None,
        speaker_mappings=_mappings_to_response(mappings),
    )


@router.put("/{job_id}/speakers", response_model=SpeakerMappingsResponse)
def update_speaker_mappings(
    job_id: str,
    body: SpeakerMappingsInput,
    settings: Settings = Depends(get_settings),
) -> SpeakerMappingsResponse:
    """Create or update speaker profile mappings for the given job."""
    job_directory = _resolve_job_directory(settings, job_id)

    profiles: dict[str, SpeakerProfile] = {}
    for pid, p in body.profiles.items():
        profiles[pid] = SpeakerProfile(
            profile_id=p.profile_id,
            name=p.name,
            organization=p.organization,
        )

    mappings = SpeakerMappings(
        profiles=profiles,
        label_to_profile=dict(body.label_to_profile),
    )
    save_speaker_mappings(job_directory, mappings=mappings)

    return _mappings_to_response(mappings)  # type: ignore[return-value]


def _is_deletable(job_directory: Path) -> bool:
    """Return True if the job is completed or failed (safe to delete)."""
    from ..job_state import load_job_failure

    try:
        if load_job_failure(job_directory) is not None:
            return True
    except Exception:
        # job_failed.json が破損していても、ファイル自体が存在すれば
        # 失敗ジョブとみなし削除を許可する
        if (job_directory / "job_failed.json").exists():
            return True
        raise
    if (job_directory / "summary_items.json").exists():
        return True
    return False


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(job_id: str, settings: Settings = Depends(get_settings)) -> Response:
    """Delete all artefacts for the specified job."""
    job_directory = _resolve_job_directory(settings, job_id)

    if not _is_deletable(job_directory):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "only completed or failed jobs can be deleted",
        )

    try:
        shutil.rmtree(job_directory)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "meeting not found") from None
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "failed to delete meeting artefacts",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{job_id}/markdown")
def get_meeting_markdown(
    job_id: str, settings: Settings = Depends(get_settings)
) -> PlainTextResponse:
    """Return meeting artefacts rendered as a Markdown document."""
    from ..job_state import load_job_title
    from ..markdown import render_meeting_markdown

    job_directory = _resolve_job_directory(settings, job_id)

    title = load_job_title(job_directory)
    segments = load_transcript_segments(job_directory)
    summary_items = load_summary_items(job_directory)
    action_items = load_action_items(job_directory)
    mappings = load_speaker_mappings(job_directory)

    md = render_meeting_markdown(
        job_id=job_id,
        title=title,
        summary_items=summary_items,
        action_items=action_items,
        segments=segments,
        speaker_mappings=mappings,
    )

    filename = f"{job_id}.md"
    return PlainTextResponse(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


__all__ = ["router"]
