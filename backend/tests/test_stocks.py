import pytest

from tests.conftest import create_user, login, seed_stock, unique_username


@pytest.mark.asyncio
async def test_stocks_require_login(client, db_session):
    await seed_stock(db_session)
    response = await client.get("/api/v1/stocks")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REQUIRED"


@pytest.mark.asyncio
async def test_stock_list_and_detail(client, db_session):
    user = await create_user(db_session, username=unique_username("stock"), password="UserPass123")
    stock = await seed_stock(db_session)
    await login(client, username=user.username, password="UserPass123")

    listed = await client.get("/api/v1/stocks", params={"q": "茅台"})
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 1
    assert listed.json()["data"]["items"][0]["symbol"] == "600519.SH"
    assert listed.json()["data"]["items"][0]["code"] == "600519"
    assert "marketSnapshot" not in listed.text

    detail = await client.get(f"/api/v1/stocks/{stock.id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == str(stock.id)

    missing = await client.get("/api/v1/stocks/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "STOCK_NOT_FOUND"
