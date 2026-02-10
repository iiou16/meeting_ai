from __future__ import annotations

from pathlib import Path

import pytest

from meetingai_backend.transcription.openai import ChunkTranscriptionResult
from meetingai_backend.transcription.segments import (
    _iter_candidate_segments,
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


def test_merge_chunk_transcriptions_raises_when_no_segments() -> None:
    """segments キーのないレスポンスで RuntimeError が発生することを検証。"""
    chunk = _make_chunk(
        asset_id="asset-c",
        start_ms=0,
        end_ms=1_000,
        text=" チャンク全体 ",
        language="en",
        response={},
    )

    with pytest.raises(RuntimeError, match="did not contain segments"):
        merge_chunk_transcriptions(job_id="job-x", chunk_results=[chunk])


def test_dump_and_load_transcript_segments(tmp_path: Path) -> None:
    chunk = _make_chunk(
        asset_id="asset-d",
        start_ms=0,
        end_ms=2_000,
        text="segment",
        language="en",
        response={
            "segments": [
                {"start": 0.0, "end": 2.0, "text": "segment"},
            ]
        },
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


class TestIterCandidateSegmentsErrorCases:
    """_iter_candidate_segments のエラーハンドリングをテストする。"""

    def test_raises_when_segments_missing(self) -> None:
        """segments が存在しない（フォールバック）場合に RuntimeError を発生させる。"""
        chunk = _make_chunk(
            asset_id="asset-no-segments",
            start_ms=0,
            end_ms=5_000,
            text="some text",
            language="ja",
            response={},  # segments キーなし
        )
        with pytest.raises(RuntimeError, match="did not contain segments"):
            list(_iter_candidate_segments(chunk))

    def test_raises_when_segments_is_none(self) -> None:
        """segments が None の場合に RuntimeError を発生させる。"""
        chunk = _make_chunk(
            asset_id="asset-none-segments",
            start_ms=0,
            end_ms=5_000,
            text="some text",
            language="ja",
            response={"segments": None},
        )
        with pytest.raises(RuntimeError, match="did not contain segments"):
            list(_iter_candidate_segments(chunk))

    def test_raises_when_segments_is_empty_list(self) -> None:
        """segments が空リストの場合に RuntimeError を発生させる。"""
        chunk = _make_chunk(
            asset_id="asset-empty-segments",
            start_ms=0,
            end_ms=5_000,
            text="some text",
            language="ja",
            response={"segments": []},
        )
        with pytest.raises(RuntimeError, match="did not contain segments"):
            list(_iter_candidate_segments(chunk))

    def test_skips_segment_without_start(self) -> None:
        """start が欠落したセグメントはスキップされる。"""
        chunk = _make_chunk(
            asset_id="asset-missing-start",
            start_ms=0,
            end_ms=5_000,
            text="fallback",
            language="ja",
            response={
                "segments": [
                    {"text": "no start", "end": 2.0},
                    {"text": "has start", "start": 2.0, "end": 4.0},
                ]
            },
        )
        candidates = list(_iter_candidate_segments(chunk))
        assert len(candidates) == 1
        assert candidates[0]["text"] == "has start"

    def test_skips_segment_with_start_gte_end(self) -> None:
        """start >= end の不正セグメントはスキップされる。

        注: この検証は merge_chunk_transcriptions 内の end_ms <= start_ms
        チェックで行われるが、_iter_candidate_segments レベルでも yield されて
        後で弾かれることを確認する。
        """
        chunk = _make_chunk(
            asset_id="asset-bad-range",
            start_ms=0,
            end_ms=10_000,
            text="fallback",
            language="ja",
            response={
                "segments": [
                    {"text": "equal", "start": 3.0, "end": 3.0},
                    {"text": "reversed", "start": 5.0, "end": 4.0},
                    {"text": "valid", "start": 1.0, "end": 2.0},
                ]
            },
        )
        segments = merge_chunk_transcriptions(
            job_id="job-test", chunk_results=[chunk]
        )
        texts = [s.text for s in segments]
        assert "valid" in texts
        # equal と reversed は end_ms <= start_ms なので除外される
        assert "equal" not in texts
        assert "reversed" not in texts
