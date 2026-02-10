"""Utilities for consolidating transcription results into transcript segments."""

from __future__ import annotations

import json
import logging
import math
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from .openai import ChunkTranscriptionResult

logger = logging.getLogger(__name__)

_SEGMENTS_FILENAME = "transcript_segments.json"


@dataclass(slots=True)
class TranscriptSegment:
    """Normalized transcription segment persisted for downstream processing."""

    segment_id: str
    job_id: str
    order: int
    start_ms: int
    end_ms: int
    text: str
    language: str | None = None
    speaker_label: str | None = None
    source_asset_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the segment to a JSON-compatible dictionary."""
        return {
            "segment_id": self.segment_id,
            "job_id": self.job_id,
            "order": self.order,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "text": self.text,
            "language": self.language,
            "speaker_label": self.speaker_label,
            "source_asset_id": self.source_asset_id,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TranscriptSegment":
        """Reconstruct a segment instance from its serialized representation."""
        return cls(
            segment_id=payload["segment_id"],
            job_id=payload["job_id"],
            order=int(payload["order"]),
            start_ms=int(payload["start_ms"]),
            end_ms=int(payload["end_ms"]),
            text=payload["text"],
            language=payload.get("language"),
            speaker_label=payload.get("speaker_label"),
            source_asset_id=payload.get("source_asset_id"),
            extra=dict(payload.get("extra") or {}),
        )

    @classmethod
    def create_id(cls) -> str:
        """Generate a new identifier for a transcript segment."""
        return uuid.uuid4().hex


def merge_chunk_transcriptions(
    *,
    job_id: str,
    chunk_results: Sequence[ChunkTranscriptionResult],
) -> list[TranscriptSegment]:
    """Merge chunk-level transcription payloads into ordered transcript segments."""
    if not chunk_results:
        return []

    ordered_chunks = sorted(
        chunk_results,
        key=lambda result: (result.start_ms, result.asset_id),
    )

    merged: list[TranscriptSegment] = []
    global_language: str | None = None
    order = 0

    for chunk in ordered_chunks:
        if chunk.language and not global_language:
            global_language = chunk.language

        for candidate in _iter_candidate_segments(chunk):
            text = candidate["text"].strip()
            if not text:
                continue

            start_ms = max(chunk.start_ms, candidate["start_ms"])
            end_ms = min(chunk.end_ms, candidate["end_ms"])

            if end_ms <= start_ms:
                continue

            language = candidate.get("language") or chunk.language or global_language

            segment = TranscriptSegment(
                segment_id=TranscriptSegment.create_id(),
                job_id=job_id,
                order=order,
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
                language=language,
                speaker_label=candidate.get("speaker_label"),
                source_asset_id=chunk.asset_id,
                extra=dict(candidate.get("extra") or {}),
            )
            merged.append(segment)
            order += 1

    if not merged:
        return merged

    # Backfill language if nothing was detected anywhere.
    if not global_language:
        for segment in merged:
            if segment.language:
                global_language = segment.language
                break

    if global_language:
        for segment in merged:
            if not segment.language:
                segment.language = global_language

    return merged


def dump_transcript_segments(
    job_directory: Path, segments: Sequence[TranscriptSegment]
) -> Path:
    """Persist transcript segments for a job into a JSON manifest."""
    job_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = job_directory / _SEGMENTS_FILENAME
    manifest_path.write_text(
        json.dumps(
            [segment.to_dict() for segment in segments], indent=2, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    return manifest_path


def load_transcript_segments(job_directory: Path) -> list[TranscriptSegment]:
    """Load previously stored transcript segments manifest for a job."""
    manifest_path = job_directory / _SEGMENTS_FILENAME
    if not manifest_path.exists():
        return []

    raw_segments = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw_segments, list):
        raise ValueError("transcript segments manifest must contain a list")

    segments: list[TranscriptSegment] = []
    for entry in raw_segments:
        if not isinstance(entry, Mapping):
            continue
        segments.append(TranscriptSegment.from_dict(entry))
    return segments


def _iter_candidate_segments(
    chunk: ChunkTranscriptionResult,
) -> Iterator[dict[str, Any]]:
    """Yield candidate segments from the raw transcription payload."""
    response = chunk.response
    segments = (
        response["segments"]
        if isinstance(response, Mapping) and "segments" in response
        else None
    )

    if not isinstance(segments, Sequence):
        raise RuntimeError(
            f"Transcription response for asset {chunk.asset_id} "
            f"(chunk {chunk.start_ms}-{chunk.end_ms} ms) did not contain "
            f"segments. Check that the model and response_format support "
            f"segment-level timestamps."
        )

    yielded = False
    for raw in segments:
        if not isinstance(raw, Mapping):
            continue

        if "text" not in raw or not isinstance(raw["text"], str):
            continue
        text: str = raw["text"]

        start_seconds = _parse_seconds(raw["start"] if "start" in raw else None)
        end_seconds = _parse_seconds(raw["end"] if "end" in raw else None)
        if start_seconds is None:
            logger.warning(
                "Skipping segment in asset %s: missing 'start' timestamp",
                chunk.asset_id,
            )
            continue
        if end_seconds is None:
            logger.warning(
                "Skipping segment in asset %s: missing 'end' timestamp",
                chunk.asset_id,
            )
            continue

        start_ms = chunk.start_ms + _seconds_to_milliseconds(start_seconds)
        end_ms = chunk.start_ms + _seconds_to_milliseconds(end_seconds)

        speaker_label: str | None = None
        if "speaker_label" in raw and isinstance(raw["speaker_label"], str):
            speaker_label = raw["speaker_label"]
        elif "speaker" in raw and isinstance(raw["speaker"], str):
            speaker_label = raw["speaker"]

        language: str | None = (
            raw["language"]
            if "language" in raw and isinstance(raw["language"], str)
            else None
        )

        candidate: dict[str, Any] = {
            "text": text,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "language": language,
            "speaker_label": speaker_label,
            "extra": _extract_segment_extra(raw),
        }
        yield candidate
        yielded = True

    if not yielded:
        raise RuntimeError(
            f"Transcription response for asset {chunk.asset_id} "
            f"(chunk {chunk.start_ms}-{chunk.end_ms} ms) did not contain "
            f"segments. The 'segments' array was empty or contained no "
            f"valid entries."
        )


def _parse_seconds(value: Any) -> float | None:
    """Best-effort conversion of segment timestamps to seconds."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _seconds_to_milliseconds(value: float) -> int:
    """Convert seconds to milliseconds while guarding against NaN/inf."""
    if math.isnan(value) or math.isinf(value):
        return 0
    return int(round(value * 1000))


def _extract_segment_extra(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Collect non-standard keys from the raw segment payload."""
    known_keys = {
        "id",
        "text",
        "start",
        "end",
        "temperature",
        "avg_logprob",
        "compression_ratio",
        "no_speech_prob",
        "speaker",
        "speaker_label",
        "language",
    }
    extra: dict[str, Any] = {}
    for key, value in raw.items():
        if key in known_keys:
            continue
        extra[key] = value
    return extra


__all__ = [
    "TranscriptSegment",
    "dump_transcript_segments",
    "load_transcript_segments",
    "merge_chunk_transcriptions",
]
