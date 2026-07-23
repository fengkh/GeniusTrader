from httpx import AsyncClient

from tests.conftest import create_user, login, seed_stock, unique_username


async def _login_user(client: AsyncClient, db_session, prefix: str = "info"):
    username = unique_username(prefix)
    await create_user(db_session, username=username, password="Password12345")
    response = await login(client, username=username, password="Password12345")
    assert response.status_code == 200


async def test_create_manual_information_with_confirmed_stock_relation(client: AsyncClient, db_session):
    await _login_user(client, db_session)
    stock = await seed_stock(db_session, symbol="300750", exchange="SZ", name="宁德时代")

    response = await client.post(
        "/api/v1/information/manual",
        json={
            "title": "用户粘贴的产业链观点",
            "text": "宁德时代发布产业链相关信息，用户需要在复盘中待核实。",
            "source_type": "social",
            "source_name": "用户补充",
            "related_stock_ids": [str(stock.id)],
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["input_type"] == "manual_text"
    assert data["status"] == "ready"
    assert data["current_content"]["content_origin"] == "user_input"
    assert data["stock_relations"][0]["relation_status"] == "confirmed"
    assert data["stock_relations"][0]["relation_origin"] == "user"


async def test_manual_information_user_isolation(client: AsyncClient, db_session):
    await _login_user(client, db_session, "owner")
    created = await client.post(
        "/api/v1/information/manual",
        json={"text": "只属于第一个用户的信息内容。", "source_type": "unknown"},
    )
    assert created.status_code == 201
    item_id = created.json()["data"]["id"]

    await _login_user(client, db_session, "other")
    response = await client.get(f"/api/v1/information/{item_id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "INFORMATION_NOT_FOUND"


async def test_user_can_confirm_reject_and_delete_stock_relations(client: AsyncClient, db_session):
    await _login_user(client, db_session)
    stock = await seed_stock(db_session, symbol="600519", exchange="SH", name="贵州茅台")
    item = await client.post(
        "/api/v1/information/manual",
        json={"text": "贵州茅台相关信息。", "source_type": "news"},
    )
    item_id = item.json()["data"]["id"]

    added = await client.post(
        f"/api/v1/information/{item_id}/stock-relations",
        json={"stock_id": str(stock.id), "relation_type": "mentioned", "evidence_text": "正文提到股票"},
    )
    assert added.status_code == 201
    relation_id = added.json()["data"]["id"]

    patched = await client.patch(
        f"/api/v1/information/{item_id}/stock-relations/{relation_id}",
        json={"relation_status": "rejected"},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["relation_status"] == "rejected"

    deleted = await client.delete(f"/api/v1/information/{item_id}/stock-relations/{relation_id}")
    assert deleted.status_code == 200
    detail = (await client.get(f"/api/v1/information/{item_id}")).json()["data"]
    assert detail["stock_relations"] == []
