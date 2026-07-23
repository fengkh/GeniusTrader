import pytest

from tests.conftest import create_user, login, seed_stock, unique_username


@pytest.mark.asyncio
async def test_user_cannot_read_modify_or_delete_other_users_watchlist(client, db_session):
    user_a = await create_user(db_session, username=unique_username("alice"), password="UserPass123")
    user_b = await create_user(db_session, username=unique_username("bob"), password="UserPass123")
    stock = await seed_stock(db_session)

    await login(client, username=user_a.username, password="UserPass123")
    item = (await client.post("/api/v1/watchlist", json={"stock_id": str(stock.id)})).json()["data"]
    await client.post("/api/v1/auth/logout")

    await login(client, username=user_b.username, password="UserPass123")
    read = await client.get(f"/api/v1/watchlist/{item['id']}")
    patch = await client.patch(f"/api/v1/watchlist/{item['id']}", json={"attention_reason": "越权"})
    delete = await client.delete(f"/api/v1/watchlist/{item['id']}")
    listed = await client.get("/api/v1/watchlist")

    assert read.status_code == 404
    assert patch.status_code == 404
    assert delete.status_code == 404
    assert listed.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_user_cannot_reference_other_users_group_or_tag(client, db_session):
    user_a = await create_user(db_session, username=unique_username("alice"), password="UserPass123")
    user_b = await create_user(db_session, username=unique_username("bob"), password="UserPass123")
    stock = await seed_stock(db_session)

    await login(client, username=user_a.username, password="UserPass123")
    group_id = (await client.post("/api/v1/watchlist/groups", json={"name": "A组"})).json()["data"]["id"]
    tag_id = (await client.post("/api/v1/watchlist/tags", json={"name": "A标签"})).json()["data"]["id"]
    await client.post("/api/v1/auth/logout")

    await login(client, username=user_b.username, password="UserPass123")
    group_reference = await client.post(
        "/api/v1/watchlist",
        json={"stock_id": str(stock.id), "group_id": group_id},
    )
    tag_reference = await client.post(
        "/api/v1/watchlist",
        json={"stock_id": str(stock.id), "tag_ids": [tag_id]},
    )

    assert group_reference.status_code == 404
    assert group_reference.json()["error"]["code"] == "GROUP_NOT_FOUND"
    assert tag_reference.status_code == 404
    assert tag_reference.json()["error"]["code"] == "TAG_NOT_FOUND"
