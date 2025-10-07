# Health-check endpoints.

from fastapi import APIRouter, status

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", status_code=status.HTTP_200_OK)
async def read_health() -> dict[str, str]:
    """Simple health-check endpoint used for readiness probes."""
    return {"status": "ok"}
