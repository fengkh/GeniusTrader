import json
from datetime import UTC, date, datetime

from httpx import AsyncClient
from sqlalchemy import select

from app.core.time import utc_now
from app.models.information import (
    InformationAnalysisVersion,
    InformationContent,
    InformationItem,
    InformationStockRelation,
    VerificationItem,
)
from app.models.review_notification import (
    BusinessEvent,
    DailyReviewItem,
    Notification,
    NotificationDelivery,
)
from app.models.stock import Stock
from tests.conftest import create_user, login, seed_stock, unique_username

REVIEW_DATE = date(2026, 7, 24)


def analysis_payload(*, stock_symbol: str = "600519") -> dict:
    return {
        "schema_version": "information-analysis-v1",
        "content_type": "news_report",
        "summary": "用户保存的信息提到公司事项。",
        "facts": [{"claim": "材料提到公司事项", "evidence_text": "材料提到公司事项", "confidence": 0.8}],
        "opinions": [
            {
                "claim": "作者认为事项需要继续观察",
                "holder": "作者",
                "rationale": "仍需正式披露",
                "time_horizon": "未来数周",
                "confidence": 0.6,
                "evidence_text": "需要继续观察",
            }
        ],
        "rumors": [
            {
                "claim": "未经证实的订单传闻",
                "verification_needed": "需要正式公告或客户订单",
                "confidence": 0.3,
                "evidence_text": "订单传闻",
            }
        ],
        "sentiment": {
            "direction": "mixed",
            "strength": "low",
            "target": "自选股",
            "confidence": 0.6,
            "rationale": "事实、观点和传闻并存",
        },
        "evidence_strength": "weak",
        "uncertainty": "high",
        "source_reliability": {"level": "medium", "reasons": ["单一来源"]},
        "key_claims": [{"claim": "关键主张", "evidence_text": "证据", "confidence": 0.6}],
        "stock_mentions": [
            {
                "symbol": stock_symbol,
                "name": "贵州茅台",
                "relation_type": "mentioned",
                "confidence": 0.9,
                "evidence_text": "提到股票",
            }
        ],
        "entity_mentions": [],
        "risks": [{"description": "传闻未核实", "severity": "high", "evidence_text": "传闻"}],
        "verification_items": [
            {
                "description": "核实是否有正式公告",
                "verification_type": "official_announcement",
                "priority": "high",
                "evidence_needed": "上市公司公告",
            }
        ],
        "time_horizon": "未来数周",
        "limitations": ["单一来源，无法外部核实"],
    }


def ai_review_payload(source_ids: list[str], *, extra_source: str | None = None) -> str:
    ids = [*source_ids]
    if extra_source:
        ids.append(extra_source)
    return json.dumps(
        {
            "schema_version": "daily-review-v1",
            "executive_summary": "当日用户私有信息复盘已生成，事实、观点和传闻保持分离。",
            "key_developments": ["有一条自选股相关信息需要复核"],
            "stock_summaries": [{"stock_id": "input-stock", "summary": "仅基于用户保存信息进行观察"}],
            "verification_focus": ["核实是否存在正式公告"],
            "tomorrow_observation_focus": ["需要确认事件是否被权威来源支持"],
            "uncertainty_summary": "仍有未经证实内容",
            "limitations": ["不代表全市场行情复盘"],
            "source_item_ids": ids,
        },
        ensure_ascii=False,
    )


async def _login_user(client: AsyncClient, db_session, prefix: str = "review"):
    user = await create_user(db_session, username=unique_username(prefix), password="Password12345")
    response = await login(client, username=user.username, password="Password12345")
    assert response.status_code == 200
    return user


async def _add_watchlist_stock(client: AsyncClient, db_session) -> Stock:
    stock = await seed_stock(db_session)
    response = await client.post(
        "/api/v1/watchlist",
        json={"stock_id": str(stock.id), "attention_reason": "验证关注逻辑"},
    )
    assert response.status_code == 201
    return stock


async def _manual_item(
    client: AsyncClient,
    *,
    text: str = "贵州茅台相关信息，需要每日复盘。",
    stock_id: str | None = None,
    published_at: datetime | None = None,
) -> str:
    response = await client.post(
        "/api/v1/information/manual",
        json={
            "title": "每日复盘测试信息",
            "text": text,
            "source_type": "news",
            "published_at": published_at.isoformat() if published_at else datetime(2026, 7, 24, 1, 0, tzinfo=UTC).isoformat(),
            "related_stock_ids": [stock_id] if stock_id else [],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


async def _insert_success_analysis(db_session, item_id: str) -> InformationAnalysisVersion:
    item = (await db_session.execute(select(InformationItem).where(InformationItem.id == item_id))).scalar_one()
    content = (
        await db_session.execute(
            select(InformationContent)
            .where(InformationContent.information_item_id == item.id)
            .order_by(InformationContent.content_version.desc())
        )
    ).scalars().first()
    assert content
    analysis = InformationAnalysisVersion(
        information_item_id=item.id,
        version_number=1,
        schema_version="information-analysis-v1",
        prompt_version="test",
        provider_config_id=None,
        model_name=None,
        analysis_status="succeeded",
        structured_result=analysis_payload(),
        input_content_hash=content.content_hash,
        created_at=utc_now(),
    )
    db_session.add(analysis)
    item.status = "analyzed"
    await db_session.flush()
    db_session.add(
        VerificationItem(
            information_item_id=item.id,
            analysis_version_id=analysis.id,
            description="核实是否有正式公告",
            verification_type="official_announcement",
            status="pending",
            priority="high",
            evidence_needed="上市公司公告",
        )
    )
    await db_session.commit()
    return analysis


async def test_empty_and_complete_rules_only_reviews(client: AsyncClient, db_session):
    await _login_user(client, db_session)

    empty = await client.post("/api/v1/reviews", json={"review_date": REVIEW_DATE.isoformat(), "use_ai": False})
    assert empty.status_code == 201
    empty_data = empty.json()["data"]
    assert empty_data["status"] == "empty"
    assert empty_data["current_version"]["generation_mode"] == "rules_only"
    assert empty_data["current_version"]["version_number"] == 1

    stock = await _add_watchlist_stock(client, db_session)
    item_id = await _manual_item(client, stock_id=str(stock.id))
    await _insert_success_analysis(db_session, item_id)

    complete = await client.post("/api/v1/reviews", json={"review_date": REVIEW_DATE.isoformat(), "use_ai": False, "force": True})
    assert complete.status_code == 201
    data = complete.json()["data"]
    snapshot = data["current_version"]["rule_snapshot"]
    assert data["status"] == "complete"
    assert data["current_version"]["version_number"] == 2
    assert snapshot["scope_note"] == "当前复盘仅聚合用户保存和分析的信息，不代表全市场行情复盘。"
    assert snapshot["overview"]["fact_count"] == 1
    assert snapshot["overview"]["rumor_count"] == 1
    assert snapshot["watchlist_sections"][0]["symbol"] == "600519"
    assert "买入" not in str(snapshot)


async def test_partial_relations_latest_success_and_non_watchlist_group(client: AsyncClient, db_session):
    await _login_user(client, db_session)
    watch_stock = await _add_watchlist_stock(client, db_session)
    non_watch_stock = await seed_stock(db_session, symbol="300750", exchange="SZ", name="宁德时代")
    analyzed_item = await _manual_item(client, stock_id=str(watch_stock.id))
    success = await _insert_success_analysis(db_session, analyzed_item)
    failed_old = InformationAnalysisVersion(
        information_item_id=success.information_item_id,
        version_number=2,
        schema_version="information-analysis-v1",
        prompt_version="test",
        analysis_status="failed",
        structured_result={"error_code": "AI_SCHEMA_VALIDATION_FAILED"},
        input_content_hash="older-failed",
        created_at=utc_now(),
    )
    db_session.add(failed_old)

    pending_item = await _manual_item(client, text="另一条尚未分析的信息。")
    pending = (await db_session.execute(select(InformationItem).where(InformationItem.id == pending_item))).scalar_one()
    db_session.add(
        InformationStockRelation(
            information_item_id=pending.id,
            stock_id=watch_stock.id,
            relation_origin="ai",
            relation_status="suggested",
            relation_type="mentioned",
            confidence=0.8,
        )
    )
    non_watch_item = await _manual_item(client, stock_id=str(non_watch_stock.id))
    await _insert_success_analysis(db_session, non_watch_item)
    await db_session.commit()

    response = await client.post("/api/v1/reviews", json={"review_date": REVIEW_DATE.isoformat(), "use_ai": False})
    assert response.status_code == 201
    snapshot = response.json()["data"]["current_version"]["rule_snapshot"]
    assert response.json()["data"]["status"] == "partial"
    assert snapshot["overview"]["pending_analysis_count"] == 1
    assert snapshot["pending_relations"][0]["symbol"] == "600519"
    assert snapshot["confirmed_non_watchlist_sections"][0]["symbol"] == "300750"
    item_rows = (await db_session.execute(select(DailyReviewItem))).scalars().all()
    assert {row.inclusion_type for row in item_rows} >= {"analyzed", "unconfirmed_relation"}
    assert str(success.id) in str(snapshot)
    assert str(failed_old.id) not in str(snapshot)


async def test_ai_review_success_fallback_idempotency_and_force(client: AsyncClient, db_session, monkeypatch):
    await _login_user(client, db_session)
    stock = await _add_watchlist_stock(client, db_session)
    item_id = await _manual_item(client, stock_id=str(stock.id))
    await _insert_success_analysis(db_session, item_id)
    provider = await client.post(
        "/api/v1/ai/providers",
        json={
            "provider_name": "Mock",
            "base_url": "http://127.0.0.1:9999/v1",
            "model_name": "mock-model",
            "api_key": "secret",
            "enabled": True,
        },
    )
    assert provider.status_code == 201
    calls = {"count": 0}

    async def fake_success(**kwargs):
        from app.services.ai_gateway import AIChatResult

        calls["count"] += 1
        assert kwargs["response_format"] == {"type": "json_object"}
        rule_snapshot = kwargs["messages"][1]["content"]
        assert "RULE_SNAPSHOT" in rule_snapshot
        return AIChatResult(
            content=f"```json\n{ai_review_payload([item_id])}\n```",
            http_status=200,
            duration_ms=10,
            input_tokens=10,
            output_tokens=10,
        )

    monkeypatch.setattr("app.services.ai_gateway.call_openai_chat_completion", fake_success)
    created = await client.post("/api/v1/reviews", json={"review_date": REVIEW_DATE.isoformat()})
    assert created.status_code == 201
    data = created.json()["data"]
    assert data["status"] == "complete"
    assert data["current_version"]["generation_mode"] == "rules_and_ai"
    assert data["current_version"]["ai_structured_result"]["executive_summary"]
    assert calls["count"] == 1

    idempotent = await client.post("/api/v1/reviews", json={"review_date": REVIEW_DATE.isoformat()})
    assert idempotent.status_code == 201
    assert idempotent.json()["data"]["current_version"]["version_number"] == 1
    assert calls["count"] == 1

    force = await client.post("/api/v1/reviews", json={"review_date": REVIEW_DATE.isoformat(), "force": True})
    assert force.json()["data"]["current_version"]["version_number"] == 2
    assert calls["count"] == 2

    async def fake_failure(**kwargs):
        from app.services.ai_gateway import AIChatResult

        return AIChatResult(content='{"schema_version":"daily-review-v1"}', http_status=200, duration_ms=10, input_tokens=1, output_tokens=1)

    monkeypatch.setattr("app.services.ai_gateway.call_openai_chat_completion", fake_failure)
    fallback = await client.post("/api/v1/reviews", json={"review_date": REVIEW_DATE.isoformat(), "force": True})
    fallback_data = fallback.json()["data"]
    assert fallback_data["status"] == "partial"
    assert fallback_data["current_version"]["generation_mode"] == "rules_with_ai_fallback"
    assert fallback_data["current_version"]["rule_snapshot"]["overview"]["total_information_count"] == 1


async def test_stale_detection_and_notifications(client: AsyncClient, db_session):
    await _login_user(client, db_session)
    stock = await _add_watchlist_stock(client, db_session)
    item_id = await _manual_item(client, stock_id=str(stock.id))
    await _insert_success_analysis(db_session, item_id)
    generated = await client.post("/api/v1/reviews", json={"review_date": REVIEW_DATE.isoformat(), "use_ai": False})
    review_id = generated.json()["data"]["id"]

    unread = await client.get("/api/v1/notifications/unread-count")
    assert unread.json()["data"]["unread_count"] == 1
    first_notification = (await client.get("/api/v1/notifications")).json()["data"]["items"][0]
    assert first_notification["deep_link"] == f"/reviews/{review_id}"
    patched = await client.patch(f"/api/v1/notifications/{first_notification['id']}", json={"action": "mark_read"})
    assert patched.json()["data"]["status"] == "read"
    await client.post("/api/v1/notifications/mark-all-read", json={})

    await _manual_item(client, text="新增同日信息导致复盘需要更新。", stock_id=str(stock.id))
    stale = await client.get(f"/api/v1/reviews/{review_id}")
    assert stale.json()["data"]["status"] == "stale"
    stale_notification = (await client.get("/api/v1/notifications", params={"event_type": "user_daily_review.became_stale"})).json()["data"]
    assert stale_notification["total"] == 1

    regenerated = await client.post(f"/api/v1/reviews/{review_id}/regenerate", params={"use_ai": "false"})
    assert regenerated.json()["data"]["status"] == "partial"
    assert regenerated.json()["data"]["stale_at"] is None

    deliveries = (await db_session.execute(select(NotificationDelivery))).scalars().all()
    assert all(delivery.status == "delivered" for delivery in deliveries)


async def test_notification_preferences_and_information_events(client: AsyncClient, db_session, monkeypatch):
    await _login_user(client, db_session)
    stock = await _add_watchlist_stock(client, db_session)
    provider = await client.post(
        "/api/v1/ai/providers",
        json={
            "provider_name": "Mock",
            "base_url": "http://127.0.0.1:9999/v1",
            "model_name": "mock-model",
            "api_key": "secret",
            "enabled": True,
        },
    )
    assert provider.status_code == 201
    item_id = await _manual_item(client, stock_id=str(stock.id))

    async def fake_analysis(**kwargs):
        from app.services.ai_gateway import AIChatResult

        return AIChatResult(
            content=json.dumps(analysis_payload(), ensure_ascii=False),
            http_status=200,
            duration_ms=10,
            input_tokens=1,
            output_tokens=1,
        )

    monkeypatch.setattr("app.services.ai_gateway.call_openai_chat_completion", fake_analysis)
    analyzed = await client.post(f"/api/v1/information/{item_id}/analyze", json={})
    assert analyzed.status_code == 200

    events = (await db_session.execute(select(BusinessEvent))).scalars().all()
    assert "information.verification_required" in {event.event_type for event in events}
    notifications = (await db_session.execute(select(Notification))).scalars().all()
    assert all(notification.event_type != "information.verification_required" for notification in notifications)

    important = await client.patch(f"/api/v1/information/{item_id}", json={"is_important": True})
    assert important.status_code == 200
    high_priority_notifications = (await client.get("/api/v1/notifications", params={"event_type": "information.high_priority_detected"})).json()["data"]
    assert high_priority_notifications["total"] == 1

    preferences = (await client.get("/api/v1/notification-preferences")).json()["data"]
    disabled_payload = {
        "items": [
            {
                **item,
                "enabled": False,
                "frequency": "disabled",
                "quiet_hours_start": item["quiet_hours_start"],
                "quiet_hours_end": item["quiet_hours_end"],
            }
            for item in preferences
            if item["event_type"] in {"user_daily_review.generated", "user_daily_review.partial"}
        ]
    }
    updated = await client.put("/api/v1/notification-preferences", json=disabled_payload)
    assert updated.status_code == 200

    before = (await client.get("/api/v1/notifications/unread-count")).json()["data"]["unread_count"]
    await client.post("/api/v1/reviews", json={"review_date": REVIEW_DATE.isoformat(), "use_ai": False, "force": True})
    after = (await client.get("/api/v1/notifications/unread-count")).json()["data"]["unread_count"]
    assert after == before


async def test_review_and_notification_user_isolation(client: AsyncClient, db_session):
    user_a = await _login_user(client, db_session, "alice")
    stock = await _add_watchlist_stock(client, db_session)
    item_id = await _manual_item(client, stock_id=str(stock.id))
    await _insert_success_analysis(db_session, item_id)
    review = await client.post("/api/v1/reviews", json={"review_date": REVIEW_DATE.isoformat(), "use_ai": False})
    review_id = review.json()["data"]["id"]
    notification_id = (await client.get("/api/v1/notifications")).json()["data"]["items"][0]["id"]
    await client.post("/api/v1/auth/logout")

    user_b = await create_user(db_session, username=unique_username("bob"), password="Password12345")
    assert user_a.id != user_b.id
    await login(client, username=user_b.username, password="Password12345")

    assert (await client.get(f"/api/v1/reviews/{review_id}")).status_code == 404
    assert (await client.post(f"/api/v1/reviews/{review_id}/regenerate")).status_code == 404
    assert (await client.get(f"/api/v1/notifications/{notification_id}")).status_code == 404
    assert (await client.patch(f"/api/v1/notifications/{notification_id}", json={"action": "mark_read"})).status_code == 404
    own_reviews = await client.get("/api/v1/reviews")
    assert own_reviews.json()["data"]["total"] == 0
    own_notifications = await client.get("/api/v1/notifications")
    assert own_notifications.json()["data"]["total"] == 0
