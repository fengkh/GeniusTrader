import json

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.errors import AppError, ErrorCode
from app.models.ai import AITask, AITaskAttempt
from app.services.information import _parse_analysis_json
from tests.conftest import create_user, login, seed_stock, unique_username


def valid_analysis_json(*, stock_symbol: str = "600519") -> str:
    return json.dumps(
        {
            "schema_version": "information-analysis-v1",
            "content_type": "news_report",
            "summary": "内容提到公司经营变化，需要核实影响范围。",
            "facts": [{"claim": "正文提到公司经营变化", "evidence_text": "正文证据", "confidence": 0.8}],
            "opinions": [
                {
                    "claim": "平台观点认为影响偏正面",
                    "holder": "平台作者",
                    "rationale": "观点依据",
                    "time_horizon": "短期",
                    "confidence": 0.6,
                    "evidence_text": "观点证据",
                }
            ],
            "rumors": [
                {
                    "claim": "未经证实的扩产传闻",
                    "verification_needed": "需要正式公告验证",
                    "confidence": 0.3,
                    "evidence_text": "传闻证据",
                }
            ],
            "sentiment": {
                "direction": "mixed",
                "strength": "medium",
                "target": "个股",
                "confidence": 0.7,
                "rationale": "事实和观点并存",
            },
            "evidence_strength": "medium",
            "uncertainty": "medium",
            "source_reliability": {"level": "medium", "reasons": ["来源为平台内容"]},
            "key_claims": [{"claim": "关键主张", "evidence_text": "证据", "confidence": 0.7}],
            "stock_mentions": [
                {
                    "symbol": stock_symbol,
                    "name": "贵州茅台",
                    "relation_type": "mentioned",
                    "confidence": 0.9,
                    "evidence_text": "提到股票",
                }
            ],
            "entity_mentions": [
                {
                    "entity_type": "industry",
                    "entity_name": "白酒",
                    "relation": "所属行业",
                    "confidence": 0.8,
                    "evidence_text": "行业证据",
                }
            ],
            "risks": [{"description": "传闻未核实", "severity": "medium", "evidence_text": "传闻证据"}],
            "verification_items": [
                {
                    "description": "核实是否有正式公告",
                    "verification_type": "official_announcement",
                    "priority": "high",
                    "evidence_needed": "上市公司公告",
                }
            ],
            "time_horizon": "短期",
            "limitations": ["AI 分析不改变原始事实"],
        },
        ensure_ascii=False,
    )


async def _login_with_provider(client: AsyncClient, db_session):
    username = unique_username("analysis")
    await create_user(db_session, username=username, password="Password12345")
    await seed_stock(db_session, symbol="600519", exchange="SH", name="贵州茅台")
    response = await login(client, username=username, password="Password12345")
    assert response.status_code == 200
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


async def test_analyze_requires_user_provider_before_creating_task(client: AsyncClient, db_session):
    username = unique_username("analysis_no_provider")
    await create_user(db_session, username=username, password="Password12345")
    response = await login(client, username=username, password="Password12345")
    assert response.status_code == 200
    item = await client.post("/api/v1/information/manual", json={"text": "需要用户自行配置 Provider 后才能分析。"})
    item_id = item.json()["data"]["id"]

    before = (await db_session.execute(select(func.count()).select_from(AITask))).scalar_one()
    response = await client.post(f"/api/v1/information/{item_id}/analyze", json={})
    after = (await db_session.execute(select(func.count()).select_from(AITask))).scalar_one()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AI_PROVIDER_REQUIRED"
    assert after == before


async def test_information_analysis_success_creates_version_and_suggestions(client: AsyncClient, db_session, monkeypatch):
    await _login_with_provider(client, db_session)
    item = await client.post(
        "/api/v1/information/manual",
        json={"text": "贵州茅台出现平台讨论，含事实、观点和未经证实传闻。", "source_type": "news"},
    )
    item_id = item.json()["data"]["id"]
    assert (await db_session.execute(select(func.count()).select_from(AITask))).scalar_one() == 0

    async def fake_call(**kwargs):
        from app.services.ai_gateway import AIChatResult

        assert kwargs["messages"][1]["content"].count("UNTRUSTED_CONTENT_START") == 1
        assert kwargs["response_format"] == {"type": "json_object"}
        return AIChatResult(
            content=valid_analysis_json(),
            http_status=200,
            duration_ms=20,
            input_tokens=100,
            output_tokens=200,
        )

    monkeypatch.setattr("app.services.ai_gateway.call_openai_chat_completion", fake_call)
    response = await client.post(f"/api/v1/information/{item_id}/analyze", json={})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "analyzed"
    assert data["latest_analysis"]["analysis_status"] == "succeeded"
    assert data["stock_relations"][0]["relation_origin"] == "ai"
    assert data["stock_relations"][0]["relation_status"] == "suggested"
    assert data["verification_items"][0]["status"] == "pending"
    assert data["latest_analysis"]["structured_result"]["rumors"][0]["claim"] == "未经证实的扩产传闻"
    tasks = (await db_session.execute(select(AITask))).scalars().all()
    assert len(tasks) == 1
    assert tasks[0].task_type == "information_sentiment_analysis"
    assert tasks[0].status == "succeeded"


async def test_metadata_only_announcement_prompt_requires_pdf_body_limitation(client: AsyncClient, db_session, monkeypatch):
    await _login_with_provider(client, db_session)
    item = await client.post(
        "/api/v1/information/manual",
        json={
            "source_type": "announcement",
            "text": "【公告元数据导入】\n当前仅导入公告元数据，未提取、补写或长期保存公告 PDF 原文。\n标题：Alpha Tech 临时公告\n限制：来源授权、完整性、及时性、稳定性及长期可用性尚未最终确认。",
        },
    )
    item_id = item.json()["data"]["id"]

    async def fake_call(**kwargs):
        from app.services.ai_gateway import AIChatResult

        prompt = kwargs["messages"][1]["content"]
        assert "Item source_type: announcement" in prompt
        assert "当前仅导入公告元数据" in prompt
        assert "If an announcement item says it is metadata_only or lacks extracted PDF text" in prompt
        assert "limitations must state that only metadata is available" in prompt
        assert "do not write or infer the missing announcement body" in prompt
        return AIChatResult(
            content=valid_analysis_json(),
            http_status=200,
            duration_ms=10,
            input_tokens=10,
            output_tokens=10,
        )

    monkeypatch.setattr("app.services.ai_gateway.call_openai_chat_completion", fake_call)
    response = await client.post(f"/api/v1/information/{item_id}/analyze", json={})

    assert response.status_code == 200
    assert response.json()["data"]["latest_analysis"]["analysis_status"] == "succeeded"


def test_analysis_schema_rejects_extra_trading_advice_field():
    payload = json.loads(valid_analysis_json())
    payload["trading_advice"] = {"action": "buy", "target_price": "not allowed"}

    with pytest.raises(AppError) as error:
        _parse_analysis_json(json.dumps(payload, ensure_ascii=False))

    assert error.value.code == ErrorCode.AI_SCHEMA_VALIDATION_FAILED


async def test_analysis_invalid_json_is_repaired_once(client: AsyncClient, db_session, monkeypatch):
    await _login_with_provider(client, db_session)
    item = await client.post("/api/v1/information/manual", json={"text": "贵州茅台信息。"})
    item_id = item.json()["data"]["id"]
    calls = {"count": 0}

    async def fake_call(**kwargs):
        from app.services.ai_gateway import AIChatResult

        calls["count"] += 1
        content = "not-json" if calls["count"] == 1 else valid_analysis_json()
        return AIChatResult(content=content, http_status=200, duration_ms=10, input_tokens=10, output_tokens=10)

    monkeypatch.setattr("app.services.ai_gateway.call_openai_chat_completion", fake_call)
    response = await client.post(f"/api/v1/information/{item_id}/analyze", json={})

    assert response.status_code == 200
    assert calls["count"] == 2
    attempts = (await db_session.execute(select(AITaskAttempt).order_by(AITaskAttempt.attempt_number))).scalars().all()
    assert [attempt.status for attempt in attempts] == ["failed", "succeeded"]


async def test_analysis_accepts_json_markdown_fence(client: AsyncClient, db_session, monkeypatch):
    await _login_with_provider(client, db_session)
    item = await client.post("/api/v1/information/manual", json={"text": "贵州茅台信息。"})
    item_id = item.json()["data"]["id"]

    async def fake_call(**kwargs):
        from app.services.ai_gateway import AIChatResult

        return AIChatResult(
            content=f"```json\n{valid_analysis_json()}\n```",
            http_status=200,
            duration_ms=10,
            input_tokens=10,
            output_tokens=10,
        )

    monkeypatch.setattr("app.services.ai_gateway.call_openai_chat_completion", fake_call)
    response = await client.post(f"/api/v1/information/{item_id}/analyze", json={})

    assert response.status_code == 200
    assert response.json()["data"]["latest_analysis"]["analysis_status"] == "succeeded"


async def test_analysis_schema_repair_receives_contract_and_errors(client: AsyncClient, db_session, monkeypatch):
    await _login_with_provider(client, db_session)
    item = await client.post("/api/v1/information/manual", json={"text": "贵州茅台信息。"})
    item_id = item.json()["data"]["id"]
    calls = {"count": 0, "repair_prompt": ""}

    async def fake_call(**kwargs):
        from app.services.ai_gateway import AIChatResult

        calls["count"] += 1
        if calls["count"] == 1:
            content = json.dumps({"summary": "missing fields"}, ensure_ascii=False)
        else:
            calls["repair_prompt"] = kwargs["messages"][1]["content"]
            content = valid_analysis_json()
        return AIChatResult(content=content, http_status=200, duration_ms=10, input_tokens=10, output_tokens=10)

    monkeypatch.setattr("app.services.ai_gateway.call_openai_chat_completion", fake_call)
    response = await client.post(f"/api/v1/information/{item_id}/analyze", json={})

    assert response.status_code == 200
    assert calls["count"] == 2
    assert "JSON_SCHEMA" in calls["repair_prompt"]
    assert "VALIDATION_ERRORS" in calls["repair_prompt"]
    assert "schema_version" in calls["repair_prompt"]
    attempts = (await db_session.execute(select(AITaskAttempt).order_by(AITaskAttempt.attempt_number))).scalars().all()
    assert attempts[0].attempt_metadata["validation_errors"]


async def test_analysis_prompt_handles_fictional_claims_and_explicit_stock_symbols(client: AsyncClient, db_session, monkeypatch):
    await _login_with_provider(client, db_session)
    item = await client.post(
        "/api/v1/information/manual",
        json={
            "text": "【虚构测试内容】材料称甲公司研究扩产，另提及贵州茅台（600519.SH）。",
            "source_type": "analyst_opinion",
        },
    )
    item_id = item.json()["data"]["id"]

    async def fake_call(**kwargs):
        from app.services.ai_gateway import AIChatResult

        prompt = kwargs["messages"][1]["content"]
        assert "Even when the source says the content is fictional" in prompt
        assert "Fictional or test-labeled content is still meaningful content" in prompt
        assert "Do not return empty facts/opinions/rumors" in prompt
        assert "limitations should usually contain 3 to 6 concrete items" in prompt
        assert "For exchange-qualified symbols like 600519.SH, put symbol as 600519" in prompt
        assert "Concise output limits" in prompt
        assert "Start the response with '{'" in prompt
        assert prompt.index("UNTRUSTED_CONTENT_START") < prompt.index("JSON_SCHEMA")
        return AIChatResult(
            content=valid_analysis_json(stock_symbol="600519"),
            http_status=200,
            duration_ms=10,
            input_tokens=10,
            output_tokens=10,
        )

    monkeypatch.setattr("app.services.ai_gateway.call_openai_chat_completion", fake_call)
    response = await client.post(f"/api/v1/information/{item_id}/analyze", json={})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["latest_analysis"]["analysis_status"] == "succeeded"
    assert data["stock_relations"][0]["relation_origin"] == "ai"


async def test_analysis_double_invalid_marks_failed_but_content_remains(client: AsyncClient, db_session, monkeypatch):
    await _login_with_provider(client, db_session)
    item = await client.post("/api/v1/information/manual", json={"text": "需要分析但 AI 返回错误。"})
    item_id = item.json()["data"]["id"]

    async def fake_call(**kwargs):
        from app.services.ai_gateway import AIChatResult

        return AIChatResult(content='{"summary": "missing fields"}', http_status=200, duration_ms=10, input_tokens=1, output_tokens=1)

    monkeypatch.setattr("app.services.ai_gateway.call_openai_chat_completion", fake_call)
    response = await client.post(f"/api/v1/information/{item_id}/analyze", json={})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "analysis_failed"
    assert data["current_content"]["extracted_text"] == "需要分析但 AI 返回错误。"
    assert data["latest_analysis"]["analysis_status"] == "failed"
