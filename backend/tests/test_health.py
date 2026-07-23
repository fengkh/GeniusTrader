import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import health as health_route


@pytest.mark.asyncio
async def test_health_live_and_ready(client):
    live = await client.get("/api/v1/health/live")
    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    assert live.headers["X-Request-ID"]

    ready = await client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ok", "database": "ok"}
    assert ready.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_health_ready_returns_503_when_database_unavailable(client, monkeypatch):
    async def fail_database_ready(session):
        del session
        raise SQLAlchemyError("simulated unavailable")

    monkeypatch.setattr(health_route, "check_database_ready", fail_database_ready)

    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert payload["error"]["request_id"]
    assert response.headers["X-Request-ID"] == payload["error"]["request_id"]
    assert "simulated unavailable" not in response.text
