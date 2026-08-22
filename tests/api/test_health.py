import asyncio

import httpx

import app.api.v1.health as health_module
from app.main import app


def test_health_returns_success_envelope(monkeypatch) -> None:
    async def healthy_postgres():
        return health_module.ServiceHealth(status="up")

    async def healthy_redis():
        return health_module.ServiceHealth(status="up")

    monkeypatch.setattr(health_module, "check_postgres", healthy_postgres)
    monkeypatch.setattr(health_module, "check_redis", healthy_redis)

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get("/api/v1/health")

    response = asyncio.run(request())

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["code"] == 200
    assert body["data"]["status"] == "healthy"
