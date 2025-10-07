from __future__ import annotations

from pathlib import Path

from meetingai_backend.transcription.openai import ChunkTranscriptionResult
from meetingai_backend.transcription.segments import (
    dump_transcript_segments,
    load_transcript_segments,
    merge_chunk_transcriptions,
)


def _make_chunk(
    *,
    asset_id: str,
    start_ms: int,
    end_ms: int,
    text: str,
    language: str | None,
    response: dict[str, object],
) -> ChunkTranscriptionResult:
    return ChunkTranscriptionResult(
        asset_id=asset_id,
        text=text,
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=end_ms - start_ms,
        language=language,
        response=response,
    )


def test_merge_chunk_transcriptions_uses_segments_when_available() -> None:
    chunk_a = _make_chunk(
        asset_id="asset-a",
        start_ms=0,
        end_ms=3_000,
        text="fallback-a",
        language="ja",
        response={
            "segments": [
                {
                    "start": 0.0,
                    "end": 1.2,
                    "text": "こんにちは",
                    "speaker": "SPEAKER_A",
                },
                {
                    "start": 1.2,
                    "end": 2.4,
                    "text": "世界",
                    "speaker_label": "SPEAKER_A",
                },
            ]
        },
    )
    chunk_b = _make_chunk(
        asset_id="asset-b",
        start_ms=3_000,
        end_ms=6_500,
        text="fallback-b",
        language=None,
        response={
            "segments": [
                {"start": "0", "end": "1.5", "text": "追加の発言"},
                {"start": 1.5, "end": 3.5, "text": "別のセグメント"},
            ]
        },
    )

    segments = merge_chunk_transcriptions(
        job_id="job-1", chunk_results=[chunk_b, chunk_a]
    )

    assert [segment.order for segment in segments] == [0, 1, 2, 3]
    assert [segment.text for segment in segments] == [
        "こんにちは",
        "世界",
        "追加の発言",
        "別のセグメント",
    ]
    assert segments[0].start_ms == 0
    assert segments[0].end_ms == 1_200
    assert segments[1].start_ms == 1_200
    assert segments[1].speaker_label == "SPEAKER_A"
    # chunk_b should inherit language detected earlier
    assert all(segment.language == "ja" for segment in segments)
    assert segments[2].start_ms == 3_000
    assert segments[3].end_ms == 6_500
    assert segments[3].source_asset_id == "asset-b"


def test_merge_chunk_transcriptions_falls_back_to_chunk_text() -> None:
    chunk = _make_chunk(
        asset_id="asset-c",
        start_ms=0,
        end_ms=1_000,
        text=" チャンク全体 ",
        language="en",
        response={},
    )

    segments = merge_chunk_transcriptions(job_id="job-x", chunk_results=[chunk])

    assert len(segments) == 1
    segment = segments[0]
    assert segment.text == "チャンク全体"
    assert segment.start_ms == 0
    assert segment.end_ms == 1_000
    assert segment.language == "en"


def test_dump_and_load_transcript_segments(tmp_path: Path) -> None:
    chunk = _make_chunk(
        asset_id="asset-d",
        start_ms=0,
        end_ms=2_000,
        text="segment",
        language="en",
        response={},
    )
    segments = merge_chunk_transcriptions(job_id="job-storage", chunk_results=[chunk])
    manifest_path = dump_transcript_segments(tmp_path, segments)

    assert manifest_path.exists()

    reloaded = load_transcript_segments(tmp_path)
    assert len(reloaded) == 1
    assert reloaded[0].text == "segment"
    assert reloaded[0].job_id == "job-storage"
    assert reloaded[0].order == 0


def test_load_transcript_segments_returns_empty_when_missing(tmp_path: Path) -> None:
    assert load_transcript_segments(tmp_path) == []
