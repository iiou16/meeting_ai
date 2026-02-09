"""Media file ingest pipeline tasks (video and audio)."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from ..media import (
    AudioExtractionConfig,
    MediaAsset,
    dump_media_assets,
    extract_audio_to_wav,
)
from ..media.chunking import AudioChunkSpec, split_wav_into_chunks
from ..settings import get_settings


def _build_master_asset(
    *,
    job_id: str,
    audio_path: Path,
    chunk_assets: Sequence[MediaAsset],
    source_file: Path,
) -> MediaAsset:
    """Create a MediaAsset entry representing the extracted audio master file."""
    first_chunk = chunk_assets[0]
    total_duration = sum(asset.duration_ms for asset in chunk_assets)
    end_ms = chunk_assets[-1].end_ms

    return MediaAsset(
        asset_id=MediaAsset.create_id(),
        job_id=job_id,
        kind="audio_master",
        path=audio_path.resolve(),
        order=-1,
        duration_ms=total_duration,
        start_ms=0,
        end_ms=end_ms,
        sample_rate=first_chunk.sample_rate,
        channels=first_chunk.channels,
        bit_depth=first_chunk.bit_depth,
        parent_asset_id=None,
        extra={"source_file_path": str(source_file.resolve())},
    )


def process_uploaded_video(*, job_id: str, source_path: str) -> dict[str, object]:
    """Process an uploaded video or audio file by extracting/converting audio and recording metadata."""
    path = Path(source_path)
    if not path.exists():
        raise FileNotFoundError(
            f"source file for job {job_id} was not found: {source_path}"
        )

    settings = get_settings()
    config = AudioExtractionConfig(ffmpeg_path=settings.ffmpeg_path)
    audio_path = extract_audio_to_wav(path, config=config)

    job_directory = path.parent
    chunk_specs: list[AudioChunkSpec] = split_wav_into_chunks(
        audio_path,
        job_id=job_id,
        parent_asset_id=None,
        output_dir=job_directory / "audio_chunks",
    )

    if not chunk_specs:
        raise RuntimeError("audio chunking produced no results")

    chunk_assets = [spec.asset for spec in chunk_specs]
    master_asset = _build_master_asset(
        job_id=job_id,
        audio_path=audio_path,
        chunk_assets=chunk_assets,
        source_file=path,
    )

    # Update parent references now that we have the master asset id.
    for chunk in chunk_assets:
        chunk.parent_asset_id = master_asset.asset_id

    assets = [master_asset, *chunk_assets]
    manifest_path = dump_media_assets(job_directory, assets)

    return {
        "job_id": job_id,
        "source_path": str(path.resolve()),
        "audio_path": str(audio_path.resolve()),
        "media_assets_path": str(manifest_path.resolve()),
        "audio_chunks": [str(spec.path.resolve()) for spec in chunk_specs],
    }


__all__ = ["process_uploaded_video"]
