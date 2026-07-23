import subprocess

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from tests.conftest import BACKEND_ROOT, create_user, login, unique_username


@pytest.mark.asyncio
async def test_cors_allows_configured_local_origin_without_wildcard(client):
    response = await client.options(
        "/api/v1/health/live",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


@pytest.mark.asyncio
async def test_audit_log_does_not_store_sensitive_password(client, db_session):
    admin = await create_user(db_session, username=unique_username("admin"), password="AdminPass123", role="admin")
    await login(client, username=admin.username, password="AdminPass123")
    await client.post(
        "/api/v1/admin/users",
        json={
            "username": unique_username("audit"),
            "display_name": "审计用户",
            "temporary_password": "TempPass12345",
        },
    )

    logs = (await db_session.execute(select(AuditLog))).scalars().all()
    serialized = " ".join(str(log.event_metadata) for log in logs)
    assert "TempPass12345" not in serialized
    assert "password_hash" not in serialized


def test_env_example_has_no_real_local_credentials():
    content = (BACKEND_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "PASSWORD@127.0.0.1" in content
    assert "root:" not in content


def test_local_database_env_is_git_ignored():
    result = subprocess.run(
        ["git", "check-ignore", "-q", ".local/database.env"],
        cwd=BACKEND_ROOT.parent,
        check=False,
    )
    assert result.returncode == 0
