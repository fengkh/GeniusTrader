from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.time import utc_now
from app.models.session import UserSession
from app.models.user import UserCredential
from tests.conftest import create_user, login, unique_username


@pytest.mark.asyncio
async def test_login_me_logout_and_cookie_security(client, db_session):
    user = await create_user(db_session, username=unique_username("auth"), password="UserPass123")

    response = await login(client, username=user.username, password="UserPass123")
    assert response.status_code == 200
    assert "token" not in response.text.lower()
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.cookies.get("geniustrader_csrf")

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["user"]["username"] == user.username

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    second_logout = await client.post("/api/v1/auth/logout")
    assert second_logout.status_code == 200

    after_logout = await client.get("/api/v1/auth/me")
    assert after_logout.status_code == 401
    assert after_logout.json()["error"]["code"] == "SESSION_REQUIRED"


@pytest.mark.asyncio
async def test_csrf_token_is_required_for_authenticated_write_requests(client, db_session):
    user = await create_user(db_session, username=unique_username("csrf"), password="UserPass123")
    assert (await login(client, username=user.username, password="UserPass123")).status_code == 200

    client.headers.pop("X-CSRF-Token", None)
    missing = await client.post("/api/v1/auth/change-password", json={})
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "CSRF_TOKEN_REQUIRED"

    client.headers["X-CSRF-Token"] = "wrong-token"
    invalid = await client.post("/api/v1/auth/change-password", json={})
    assert invalid.status_code == 403
    assert invalid.json()["error"]["code"] == "CSRF_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_login_rejects_disallowed_origin(client, db_session):
    user = await create_user(db_session, username=unique_username("origin"), password="UserPass123")

    response = await client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "UserPass123"},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_invalid_credentials_do_not_reveal_user_existence(client, db_session):
    user = await create_user(db_session, username=unique_username("auth"), password="UserPass123")
    wrong_password = await login(client, username=user.username, password="WrongPass123")
    missing_user = await login(client, username="missing_user", password="WrongPass123")

    assert wrong_password.status_code == 401
    assert missing_user.status_code == 401
    assert wrong_password.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert missing_user.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_failures_lock_temporarily_and_expire(client, db_session):
    user = await create_user(db_session, username=unique_username("lock"), password="UserPass123")
    for _ in range(4):
        response = await login(client, username=user.username, password="WrongPass123")
        assert response.status_code == 401

    locked = await login(client, username=user.username, password="WrongPass123")
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "ACCOUNT_LOCKED"

    still_locked = await login(client, username=user.username, password="UserPass123")
    assert still_locked.status_code == 429

    credential = (
        await db_session.execute(select(UserCredential).where(UserCredential.user_id == user.id))
    ).scalar_one()
    credential.locked_until = utc_now() - timedelta(seconds=1)
    await db_session.commit()

    recovered = await login(client, username=user.username, password="UserPass123")
    assert recovered.status_code == 200


@pytest.mark.asyncio
async def test_disabled_user_cannot_login(client, db_session):
    user = await create_user(
        db_session,
        username=unique_username("disabled"),
        password="UserPass123",
        status="disabled",
    )

    response = await login(client, username=user.username, password="UserPass123")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"


@pytest.mark.asyncio
async def test_change_password_revokes_other_sessions_but_keeps_current(db_session):
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    user = await create_user(db_session, username=unique_username("changepw"), password="UserPass123")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as first:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as second:
            assert (await login(first, username=user.username, password="UserPass123")).status_code == 200
            assert (await login(second, username=user.username, password="UserPass123")).status_code == 200

            changed = await first.post(
                "/api/v1/auth/change-password",
                json={"current_password": "UserPass123", "new_password": "NewPass12345"},
            )
            assert changed.status_code == 200
            assert (await first.get("/api/v1/auth/me")).status_code == 200
            assert (await second.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_change_password_validation(client, db_session):
    user = await create_user(db_session, username=unique_username("weakpw"), password="UserPass123")
    await login(client, username=user.username, password="UserPass123")

    wrong_current = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WrongPass123", "new_password": "NewPass12345"},
    )
    assert wrong_current.status_code == 401

    weak = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "UserPass123", "new_password": "password"},
    )
    assert weak.status_code == 422


@pytest.mark.asyncio
async def test_expired_session_returns_session_expired(client, db_session):
    user = await create_user(db_session, username=unique_username("expired"), password="UserPass123")
    assert (await login(client, username=user.username, password="UserPass123")).status_code == 200
    session_row = (await db_session.execute(select(UserSession))).scalars().one()
    session_row.expires_at = utc_now() - timedelta(seconds=1)
    await db_session.commit()

    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"
