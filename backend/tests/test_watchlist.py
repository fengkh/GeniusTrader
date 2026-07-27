import uuid

import pytest
from sqlalchemy import select

from app.models.stock import Stock
from app.models.watchlist import UserWatchlistItem
from tests.conftest import create_user, login, seed_stock, unique_username


@pytest.mark.asyncio
async def test_groups_tags_and_watchlist_crud(client, db_session):
    user = await create_user(db_session, username=unique_username("wl"), password="UserPass123")
    stock = await seed_stock(db_session)
    await login(client, username=user.username, password="UserPass123")

    groups = await client.get("/api/v1/watchlist/groups")
    assert groups.status_code == 200
    default_group = groups.json()["data"][0]
    assert default_group["name"] == "默认分组"

    created_group = await client.post("/api/v1/watchlist/groups", json={"name": "  观察组  "})
    assert created_group.status_code == 201
    group_id = created_group.json()["data"]["id"]

    duplicate_group = await client.post("/api/v1/watchlist/groups", json={"name": "观察组"})
    assert duplicate_group.status_code == 409

    tag = await client.post("/api/v1/watchlist/tags", json={"name": "  长期跟踪  "})
    assert tag.status_code == 201
    tag_id = tag.json()["data"]["id"]
    duplicate_tag = await client.post("/api/v1/watchlist/tags", json={"name": "长期跟踪"})
    assert duplicate_tag.status_code == 409

    added = await client.post(
        "/api/v1/watchlist",
        json={
            "stock_id": str(stock.id),
            "group_id": group_id,
            "attention_reason": "验证核心逻辑",
            "notes": "只做测试数据",
            "tag_ids": [tag_id, tag_id],
        },
    )
    assert added.status_code == 201
    item = added.json()["data"]
    assert item["stock"]["symbol"] == "600519.SH"
    assert item["group"]["id"] == group_id
    assert len(item["tags"]) == 1

    duplicate = await client.post("/api/v1/watchlist", json={"stock_id": str(stock.id)})
    assert duplicate.status_code == 201
    assert duplicate.json()["data"]["id"] == item["id"]

    listed = await client.get("/api/v1/watchlist", params={"q": "验证"})
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 1

    patched = await client.patch(
        f"/api/v1/watchlist/{item['id']}",
        json={"attention_reason": "更新后的关注原因", "tag_ids": []},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["attention_reason"] == "更新后的关注原因"
    assert patched.json()["data"]["tags"] == []

    deleted = await client.delete(f"/api/v1/watchlist/{item['id']}")
    assert deleted.status_code == 204
    repeated_delete = await client.delete(f"/api/v1/watchlist/{item['id']}")
    assert repeated_delete.status_code == 204

    after_delete = await client.get("/api/v1/watchlist")
    assert after_delete.json()["data"]["total"] == 0

    restored = await client.post(
        "/api/v1/watchlist",
        json={
            "stock_id": str(stock.id),
            "group_id": group_id,
            "attention_reason": "恢复关注",
            "tag_ids": [tag_id],
        },
    )
    assert restored.status_code == 201
    assert restored.json()["data"]["id"] == item["id"]
    assert restored.json()["data"]["archived_at"] is None


@pytest.mark.asyncio
async def test_default_group_cannot_be_deleted_and_group_with_items_requires_move(client, db_session):
    user = await create_user(db_session, username=unique_username("grp"), password="UserPass123")
    stock = await seed_stock(db_session)
    await login(client, username=user.username, password="UserPass123")
    default_group = (await client.get("/api/v1/watchlist/groups")).json()["data"][0]
    group = (await client.post("/api/v1/watchlist/groups", json={"name": "非默认"})).json()["data"]
    item = await client.post(
        "/api/v1/watchlist",
        json={"stock_id": str(stock.id), "group_id": group["id"]},
    )
    assert item.status_code == 201

    default_delete = await client.delete(f"/api/v1/watchlist/groups/{default_group['id']}")
    assert default_delete.status_code == 422

    no_move = await client.delete(f"/api/v1/watchlist/groups/{group['id']}")
    assert no_move.status_code == 422

    moved = await client.delete(
        f"/api/v1/watchlist/groups/{group['id']}",
        params={"move_to_group_id": default_group["id"]},
    )
    assert moved.status_code == 200


@pytest.mark.asyncio
async def test_delete_tag_only_removes_association(client, db_session):
    user = await create_user(db_session, username=unique_username("tag"), password="UserPass123")
    stock = await seed_stock(db_session)
    await login(client, username=user.username, password="UserPass123")
    tag_id = (await client.post("/api/v1/watchlist/tags", json={"name": "跟踪"})).json()["data"]["id"]
    item = (
        await client.post(
            "/api/v1/watchlist",
            json={"stock_id": str(stock.id), "tag_ids": [tag_id]},
        )
    ).json()["data"]

    deleted = await client.delete(f"/api/v1/watchlist/tags/{tag_id}")
    assert deleted.status_code == 200

    fetched = await client.get(f"/api/v1/watchlist/{item['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["tags"] == []


@pytest.mark.asyncio
async def test_watchlist_limit(client, db_session):
    user = await create_user(db_session, username=unique_username("limit"), password="UserPass123")
    await login(client, username=user.username, password="UserPass123")
    default_group = (await client.get("/api/v1/watchlist/groups")).json()["data"][0]
    stocks = []
    for index in range(201):
        stock = Stock(
            symbol=f"{index:06d}.SZ",
            code=f"{index:06d}",
            exchange="SZ",
            name=f"测试股票{index}",
            market="A_SHARE",
            board="main_board",
            security_type="common_stock",
            short_name=f"测试股票{index}",
            full_name=f"测试股票{index}",
            listing_status="active",
            aliases=[f"测试股票{index}"],
            source_code="test_seed",
            source_record_id=f"{index:06d}.SZ",
            data_completeness="usable",
            is_searchable=True,
            list_status="listed",
            currency="CNY",
            data_source="test_seed",
        )
        db_session.add(stock)
        stocks.append(stock)
    await db_session.flush()
    for stock in stocks[:200]:
        db_session.add(
            UserWatchlistItem(
                user_id=user.id,
                stock_id=stock.id,
                group_id=uuid.UUID(default_group["id"]),
                sort_order=0,
            )
        )
    await db_session.commit()

    exceeded = await client.post("/api/v1/watchlist", json={"stock_id": str(stocks[200].id)})
    assert exceeded.status_code == 429
    assert exceeded.json()["error"]["code"] == "WATCHLIST_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_seed_development_is_idempotent(monkeypatch, db_session):
    from app.cli.seed_development import _seed

    monkeypatch.setenv("APP_ENV", "development")
    assert await _seed() == 0
    assert await _seed() == 0
    count = (await db_session.execute(select(Stock))).scalars().all()
    assert len(count) == 4
