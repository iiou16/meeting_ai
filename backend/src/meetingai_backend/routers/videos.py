# Media file upload endpoints (video and audio).

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from ..jobs import JobQueueProtocol, enqueue_video_ingest_job, get_job_queue
from ..settings import Settings, get_settings

router = APIRouter(prefix="/api/videos", tags=["videos"])

_ALLOWED_FALLBACK_CONTENT_TYPES = {"application/octet-stream"}
_CHUNK_SIZE = 1024 * 1024


def _get_job_queue(settings: Settings = Depends(get_settings)) -> JobQueueProtocol:
    return get_job_queue(settings)


async def _persist_upload(file: UploadFile, destination: Path) -> None:
    """Stream the uploaded file to the destination path."""
    try:
        with destination.open("wb") as buffer:
            while chunk := await file.read(_CHUNK_SIZE):
                buffer.write(chunk)
    except OSError as exc:  # pragma: no cover - surfaced in tests
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store uploaded file.",
        ) from exc
    finally:
        await file.close()


async def upload_video(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    job_queue: JobQueueProtocol = Depends(_get_job_queue),
) -> dict[str, str]:
    """Accept a video or audio file upload and enqueue it for processing."""
    if not file.filename:
        await file.close()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must include a filename.",
        )

    if file.content_type and (
        not file.content_type.startswith("video/")
        and not file.content_type.startswith("audio/")
        and file.content_type not in _ALLOWED_FALLBACK_CONTENT_TYPES
    ):
        await file.close()
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported media type. Please upload a video or audio file.",
        )

    job_id = uuid4()
    destination_dir = settings.upload_root / str(job_id)
    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - filesystem failure
        await file.close()
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialise storage for uploaded file.",
        ) from exc

    sanitized_name = Path(file.filename).name
    destination_path = destination_dir / sanitized_name

    await _persist_upload(file, destination_path)
    enqueue_video_ingest_job(
        queue=job_queue,
        job_id=str(job_id),
        source_path=str(destination_path),
    )

    return {"job_id": str(job_id)}


router.add_api_route(
    "",
    upload_video,
    methods=["POST"],
    status_code=status.HTTP_202_ACCEPTED,
    response_model=dict[str, str],
    summary="Upload video or audio file for transcription processing",
)

__all__ = ["router"]
