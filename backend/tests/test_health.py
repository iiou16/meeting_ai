import pytest
from httpx import ASGITransport, AsyncClient

from meetingai_backend.app import create_app


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok() -> None:
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
