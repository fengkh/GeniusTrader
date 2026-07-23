from httpx import AsyncClient

from tests.conftest import create_user, login, seed_stock, unique_username


async def _login_user(client: AsyncClient, db_session):
    username = unique_username("list")
    await create_user(db_session, username=username, password="Password12345")
    response = await login(client, username=username, password="Password12345")
    assert response.status_code == 200


async def test_information_list_filters_by_source_status_flags_and_stock(client: AsyncClient, db_session):
    await _login_user(client, db_session)
    stock = await seed_stock(db_session, symbol="000001", exchange="SZ", name="平安银行")
    related = await client.post(
        "/api/v1/information/manual",
        json={
            "title": "银行公告",
            "text": "平安银行公告内容。",
            "source_type": "announcement",
            "related_stock_ids": [str(stock.id)],
        },
    )
    other = await client.post(
        "/api/v1/information/manual",
        json={"title": "平台观点", "text": "平台观点内容。", "source_type": "social"},
    )
    related_id = related.json()["data"]["id"]
    other_id = other.json()["data"]["id"]
    await client.patch(f"/api/v1/information/{related_id}", json={"is_important": True, "is_read": True})
    await client.patch(f"/api/v1/information/{other_id}", json={"archived": True})

    by_stock = await client.get(f"/api/v1/information?stock_id={stock.id}")
    assert by_stock.status_code == 200
    assert by_stock.json()["data"]["total"] == 1

    important = await client.get("/api/v1/information?source_type=announcement&is_important=true&is_read=true")
    assert important.json()["data"]["total"] == 1
    assert important.json()["data"]["items"][0]["title"] == "银行公告"

    default_list = await client.get("/api/v1/information")
    assert default_list.json()["data"]["total"] == 1
