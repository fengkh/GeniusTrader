import getpass

import pytest

from tests.conftest import create_user, login, unique_username


@pytest.mark.asyncio
async def test_admin_cli_create_admin(monkeypatch, db_session):
    from app.cli.create_admin import _create_admin
    from app.repositories.users import get_user_by_username

    username = unique_username("admincli")
    inputs = iter([username, "CLI 管理员"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    monkeypatch.setattr(getpass, "getpass", lambda _: "StrongAdmin123")

    exit_code = await _create_admin()
    assert exit_code == 0

    user = await get_user_by_username(db_session, username)
    assert user is not None
    assert user.role == "admin"
    assert user.credential.password_hash != "StrongAdmin123"


@pytest.mark.asyncio
async def test_admin_api_creates_regular_user(client, db_session):
    admin = await create_user(db_session, username=unique_username("admin"), password="AdminPass123", role="admin")
    await login(client, username=admin.username, password="AdminPass123")

    response = await client.post(
        "/api/v1/admin/users",
        json={
            "username": "NewUser",
            "display_name": "新用户",
            "temporary_password": "TempPass12345",
        },
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["username"] == "newuser"
    assert body["role"] == "user"
    assert body["must_change_password"] is True
    assert "password_hash" not in body
    assert "temporary_password" not in response.text


@pytest.mark.asyncio
async def test_regular_user_cannot_create_user(client, db_session):
    user = await create_user(db_session, username=unique_username("regular"), password="UserPass123")
    await login(client, username=user.username, password="UserPass123")

    response = await client.post(
        "/api/v1/admin/users",
        json={
            "username": "blocked",
            "display_name": "blocked",
            "temporary_password": "TempPass12345",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_duplicate_username_returns_business_error(client, db_session):
    admin = await create_user(db_session, username=unique_username("admin"), password="AdminPass123", role="admin")
    await create_user(db_session, username="dupe_user", password="UserPass123")
    await login(client, username=admin.username, password="AdminPass123")

    response = await client.post(
        "/api/v1/admin/users",
        json={
            "username": "DUPE_USER",
            "display_name": "重复用户",
            "temporary_password": "TempPass12345",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USERNAME_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_disabled_admin_cannot_create_user(client, db_session):
    admin = await create_user(
        db_session,
        username=unique_username("disabled_admin"),
        password="AdminPass123",
        role="admin",
        status="disabled",
    )

    response = await login(client, username=admin.username, password="AdminPass123")
    assert response.status_code == 403
