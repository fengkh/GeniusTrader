import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.time import utc_now
from app.models.market_data import StockDailySnapshot
from app.models.research import ResearchTask, ResearchTaskUpdate
from app.models.review_notification import BusinessEvent
from app.services.information import _parse_analysis_json
from tests.conftest import create_user, login, seed_stock, unique_username

WORKBENCH_DATE = date(2026, 7, 28)


async def _login_user(client, db_session, prefix: str = "research"):
    user = await create_user(db_session, username=unique_username(prefix), password="Password12345")
    response = await login(client, username=user.username, password="Password12345")
    assert response.status_code == 200
    return user


async def _add_watchlist_stock(client, db_session):
    stock = await seed_stock(db_session)
    response = await client.post(
        "/api/v1/watchlist",
        json={"stock_id": str(stock.id), "attention_reason": "跟踪公告和待核实事项"},
    )
    assert response.status_code == 201
    return stock


async def _add_named_watchlist_stock(client, db_session, *, symbol: str, exchange: str, name: str):
    stock = await seed_stock(db_session, symbol=symbol, exchange=exchange, name=name)
    response = await client.post(
        "/api/v1/watchlist",
        json={"stock_id": str(stock.id), "attention_reason": f"track {symbol}"},
    )
    assert response.status_code == 201
    return stock


def _snapshot(stock_id, *, close: str, pct_change: str, amount: str | None, completeness: str = "complete") -> StockDailySnapshot:
    fetched_at = utc_now()
    return StockDailySnapshot(
        stock_id=stock_id,
        source_code="MOCK_MARKET_DATA",
        trade_date=WORKBENCH_DATE,
        open=Decimal(close) - Decimal("0.20"),
        high=Decimal(close) + Decimal("0.50"),
        low=Decimal(close) - Decimal("0.80"),
        close=Decimal(close),
        pre_close=Decimal(close) - Decimal("0.10"),
        change=Decimal(close) - (Decimal(close) - Decimal("0.10")),
        pct_change=Decimal(pct_change),
        volume=Decimal("1000000"),
        amount=Decimal(amount) if amount is not None else None,
        turnover_rate=None if completeness == "partial" else Decimal("2.50"),
        volume_ratio=None,
        total_market_value=Decimal("10000000000"),
        circulating_market_value=Decimal("8000000000"),
        pe_ttm=None,
        pb=None,
        is_trading=True,
        data_completeness=completeness,
        source_updated_at=fetched_at,
        fetched_at=fetched_at,
        raw_metadata_hash=f"snapshot-{stock_id}-{close}",
        limitations=[],
        source_record_ref=f"test:{stock_id}",
    )


async def _manual_information(client, *, stock_id: str, source_type: str = "announcement") -> str:
    response = await client.post(
        "/api/v1/information/manual",
        json={
            "title": "研究工作台测试公告",
            "text": "公司公告称存在需要跟踪的事项，用户需等待后续正式披露验证。",
            "source_type": source_type,
            "published_at": datetime(2026, 7, 28, 2, 0, tzinfo=UTC).isoformat(),
            "related_stock_ids": [stock_id],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


@pytest.mark.asyncio
async def test_research_task_crud_idempotency_status_flow_and_user_isolation(client, db_session):
    await _login_user(client, db_session)
    stock = await _add_watchlist_stock(client, db_session)
    item_id = await _manual_information(client, stock_id=str(stock.id))

    payload = {
        "stock_id": str(stock.id),
        "task_type": "observation",
        "title": "观察正式披露是否出现",
        "description": "从信息分析建议采纳的观察条件，等待正式披露验证。",
        "status": "monitoring",
        "priority": "high",
        "source_type": "information_analysis",
        "source_information_item_id": item_id,
        "due_date": WORKBENCH_DATE.isoformat(),
        "current_evidence_summary": "来源信息已保存，仍需正式公告验证。",
        "suggestion_identifier": "same-suggestion",
    }
    first = await client.post("/api/v1/research-tasks", json=payload)
    assert first.status_code == 201
    first_task = first.json()["data"]

    repeated = await client.post("/api/v1/research-tasks", json=payload)
    assert repeated.status_code == 201
    assert repeated.json()["data"]["id"] == first_task["id"]
    assert (await db_session.execute(select(func.count()).select_from(ResearchTask))).scalar_one() == 1

    listed = await client.get("/api/v1/research-tasks", params={"open_only": True})
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 1

    updated = await client.post(
        f"/api/v1/research-tasks/{first_task['id']}/status",
        json={"status": "partially_confirmed", "note": "已有部分披露，但核心事项仍未完全确认。"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "partially_confirmed"
    assert updated.json()["data"]["resolved_at"] is not None
    assert len(updated.json()["data"]["updates"]) >= 2

    assert (await db_session.execute(select(func.count()).select_from(ResearchTaskUpdate))).scalar_one() >= 2
    event_types = [
        row.event_type
        for row in (await db_session.execute(select(BusinessEvent).order_by(BusinessEvent.created_at))).scalars()
    ]
    assert "research_task.created" in event_types
    assert "research_task.status_changed" in event_types

    other = await _login_user(client, db_session, prefix="other_research")
    assert other.id != first_task["user_id"]
    cross_user_list = await client.get("/api/v1/research-tasks", params={"open_only": False})
    assert cross_user_list.status_code == 200
    assert cross_user_list.json()["data"]["total"] == 0
    cross_user_get = await client.get(f"/api/v1/research-tasks/{first_task['id']}")
    assert cross_user_get.status_code == 404


@pytest.mark.asyncio
async def test_today_overview_watchlist_scanner_and_stock_dossier(client, db_session):
    await _login_user(client, db_session)
    stock = await _add_watchlist_stock(client, db_session)
    item_id = await _manual_information(client, stock_id=str(stock.id), source_type="announcement")
    await client.post(
        "/api/v1/research-tasks",
        json={
            "stock_id": str(stock.id),
            "task_type": "verification",
            "title": "核实公告后续披露",
            "description": "需要确认后续公告是否补充披露。",
            "priority": "high",
            "source_type": "announcement",
            "source_information_item_id": item_id,
            "due_date": WORKBENCH_DATE.isoformat(),
        },
    )
    await client.post(
        "/api/v1/research-tasks",
        json={
            "stock_id": str(stock.id),
            "task_type": "observation",
            "title": "观察条件到期验证",
            "description": "今日需要验证观察条件是否发生。",
            "status": "monitoring",
            "priority": "medium",
            "source_type": "daily_review",
            "due_date": WORKBENCH_DATE.isoformat(),
        },
    )

    today = await client.get("/api/v1/today/overview", params={"business_date": WORKBENCH_DATE.isoformat()})
    assert today.status_code == 200
    today_data = today.json()["data"]
    assert today_data["overview"]["watchlist_count"] == 1
    assert today_data["overview"]["open_research_task_count"] == 2
    assert today_data["overview"]["due_observation_count"] == 1
    assert today_data["priority_stocks"][0]["priority_score"] > 0
    assert any(item["title"] == "今日观察条件" for item in today_data["action_items"])

    scanner = await client.get("/api/v1/watchlist/scanner", params={"has_open_task": True})
    assert scanner.status_code == 200
    scanner_row = scanner.json()["data"]["items"][0]
    assert scanner_row["stock_id"] == str(stock.id)
    assert scanner_row["high_priority_task_count"] == 1
    assert scanner_row["attention_reasons"]

    dossier = await client.get(f"/api/v1/stocks/{stock.id}/research-dossier")
    assert dossier.status_code == 200
    dossier_data = dossier.json()["data"]
    assert dossier_data["identity"]["id"] == str(stock.id)
    assert dossier_data["current_state"]["open_task_count"] == 2
    assert len(dossier_data["official_information"]) == 1
    assert len(dossier_data["research_tasks"]) == 2
    assert any(entry["event_type"] == "research_task.created" for entry in dossier_data["timeline"])


@pytest.mark.asyncio
async def test_real_daily_snapshot_enters_today_scanner_and_dossier_without_mock_numbers(client, db_session):
    await _login_user(client, db_session, prefix="research_market")
    up_stock = await _add_named_watchlist_stock(client, db_session, symbol="600519", exchange="SH", name="Alpha Daily")
    down_stock = await _add_named_watchlist_stock(client, db_session, symbol="300750", exchange="SZ", name="Beta Daily")
    empty_stock = await _add_named_watchlist_stock(client, db_session, symbol="688981", exchange="SH", name="Gamma Empty")
    db_session.add_all(
        [
            _snapshot(up_stock.id, close="10.50", pct_change="5.26", amount="20000000"),
            _snapshot(down_stock.id, close="18.80", pct_change="-1.05", amount=None, completeness="partial"),
        ]
    )
    await db_session.commit()

    today = await client.get("/api/v1/today/overview", params={"business_date": WORKBENCH_DATE.isoformat()})
    assert today.status_code == 200
    overview = today.json()["data"]["overview"]
    assert overview["watchlist_count"] == 3
    assert overview["market_trade_date"] == WORKBENCH_DATE.isoformat()
    assert overview["market_snapshot_count"] == 2
    assert overview["market_data_unavailable_count"] == 1
    assert overview["gainers_count"] == 1
    assert overview["decliners_count"] == 1
    assert overview["market_data_status"] == "partial"
    priority_by_symbol = {row["symbol"]: row for row in today.json()["data"]["priority_stocks"]}
    assert priority_by_symbol["600519.SH"]["pct_change"] == "5.260000"
    assert any("真实日级行情" in reason for reason in priority_by_symbol["600519.SH"]["priority_reasons"])

    sorted_scanner = await client.get("/api/v1/watchlist/scanner", params={"sort": "pct_change"})
    assert sorted_scanner.status_code == 200
    sorted_rows = sorted_scanner.json()["data"]["items"]
    assert [row["symbol"] for row in sorted_rows] == ["600519.SH", "300750.SZ", "688981.SH"]
    assert sorted_rows[1]["freshness_status"] == "partial"
    assert sorted_rows[1]["amount"] is None

    up_only = await client.get("/api/v1/watchlist/scanner", params={"market_movement": "up"})
    assert up_only.status_code == 200
    assert [row["symbol"] for row in up_only.json()["data"]["items"]] == ["600519.SH"]

    no_quote = await client.get("/api/v1/watchlist/scanner", params={"market_data_available": False})
    assert no_quote.status_code == 200
    assert [row["symbol"] for row in no_quote.json()["data"]["items"]] == ["688981.SH"]

    dossier = await client.get(f"/api/v1/stocks/{down_stock.id}/research-dossier")
    assert dossier.status_code == 200
    market_snapshot = dossier.json()["data"]["market_snapshot"]
    assert market_snapshot["status"] == "partial"
    assert "amount" in market_snapshot["missing_fields"]
    assert market_snapshot["snapshot"]["pct_change"] == "-1.050000"

    empty_dossier = await client.get(f"/api/v1/stocks/{empty_stock.id}/research-dossier")
    assert empty_dossier.status_code == 200
    assert empty_dossier.json()["data"]["market_snapshot"]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_observation_resolution_enters_next_daily_review_rule_snapshot(client, db_session):
    await _login_user(client, db_session)
    stock = await _add_watchlist_stock(client, db_session)
    created = await client.post(
        "/api/v1/research-tasks",
        json={
            "stock_id": str(stock.id),
            "task_type": "observation",
            "title": "观察是否出现正式披露",
            "description": "从上一日复盘采纳的事实验证条件。",
            "status": "monitoring",
            "priority": "medium",
            "source_type": "daily_review",
            "due_date": WORKBENCH_DATE.isoformat(),
        },
    )
    assert created.status_code == 201
    task_id = created.json()["data"]["id"]
    changed = await client.post(
        f"/api/v1/research-tasks/{task_id}/status",
        json={"status": "confirmed", "note": "正式披露已经出现。"},
    )
    assert changed.status_code == 200

    review = await client.post(
        "/api/v1/reviews",
        json={"review_date": WORKBENCH_DATE.isoformat(), "use_ai": False, "force": True},
    )
    assert review.status_code == 201
    snapshot = review.json()["data"]["current_version"]["rule_snapshot"]
    assert snapshot["research_tasks"][0]["task_id"] == task_id
    assert snapshot["observation_verification_results"][0]["status"] == "confirmed"
    assert snapshot["overview"]["observation_verification_result_count"] == 1
    assert "交易建议" not in json.dumps(snapshot, ensure_ascii=False)


@pytest.mark.asyncio
async def test_information_ai_schema_accepts_research_suggestions_without_auto_creating_tasks(db_session):
    content = {
        "schema_version": "information-analysis-v1",
        "content_type": "news_report",
        "summary": "材料包含事实和未确认事项。",
        "facts": [{"claim": "材料称事项已被提及", "evidence_text": "事项被提及", "confidence": 0.8}],
        "opinions": [],
        "rumors": [],
        "sentiment": {
            "direction": "neutral",
            "strength": "low",
            "target": None,
            "confidence": 0.5,
            "rationale": "仅能确认材料表述。",
        },
        "evidence_strength": "medium",
        "uncertainty": "medium",
        "source_reliability": {"level": "medium", "reasons": ["单一来源"]},
        "key_claims": [{"claim": "关键主张", "evidence_text": "证据", "confidence": 0.7}],
        "confirmed_facts": [{"claim": "原文直接确认的事实", "evidence_text": "证据", "confidence": 0.8}],
        "key_changes": ["新增正式披露线索"],
        "affected_dimensions": ["company"],
        "relation_to_focus_reason": "direct",
        "stock_mentions": [],
        "entity_mentions": [],
        "risks": [],
        "verification_items": [],
        "suggested_research_tasks": [
            {
                "task_type": "verification",
                "title": "核实正式披露",
                "reason": "仍需确认公告正文",
                "priority": "high",
                "related_fact_indexes": [0],
                "suggested_due_date": None,
            }
        ],
        "suggested_observation_conditions": [
            {
                "title": "观察披露是否补充",
                "observation_condition": "出现补充公告",
                "verification_method": "检查公告候选和信息中心",
                "priority": "medium",
                "related_fact_indexes": [0],
                "suggested_due_date": None,
            }
        ],
        "open_questions": ["后续公告是否补充正文"],
        "source_coverage": "partial_text",
        "time_horizon": None,
        "limitations": ["单一来源"],
    }
    parsed = _parse_analysis_json(json.dumps(content, ensure_ascii=False))
    assert parsed.suggested_research_tasks[0].title == "核实正式披露"
    assert parsed.suggested_observation_conditions[0].observation_condition == "出现补充公告"
    assert (await db_session.execute(select(func.count()).select_from(ResearchTask))).scalar_one() == 0


def test_frontend_workbench_contracts_are_present():
    repo_root = Path(__file__).resolve().parents[2]
    today_page = (repo_root / "src/app/today/page.tsx").read_text(encoding="utf-8")
    watchlist_page = (repo_root / "src/app/watchlist/page.tsx").read_text(encoding="utf-8")
    dossier_page = (repo_root / "src/app/watchlist/[stockId]/page.tsx").read_text(encoding="utf-8")
    tasks_page = (repo_root / "src/app/information/tasks/page.tsx").read_text(encoding="utf-8")
    review_page = (repo_root / "src/app/reviews/[reviewId]/page.tsx").read_text(encoding="utf-8")

    assert "getTodayOverview" in today_page
    assert "getWatchlistScanner" in watchlist_page
    assert "getStockResearchDossier" in dossier_page
    assert "listResearchTasks" in tasks_page
    assert "createResearchTask" in review_page
    combined = "\n".join([today_page, watchlist_page, dossier_page, tasks_page, review_page])
    assert "/chat" not in combined
    assert "conversation" not in combined.lower()
