from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.encryption import get_secret_cipher
from app.models.ai import AIProviderConfig
from tests.conftest import create_user, login, unique_username


async def _login_user(client: AsyncClient, db_session):
    username = unique_username("ai")
    await create_user(db_session, username=username, password="Password12345")
    response = await login(client, username=username, password="Password12345")
    assert response.status_code == 200


async def test_provider_api_key_is_encrypted_and_not_returned(client: AsyncClient, db_session):
    await _login_user(client, db_session)

    response = await client.post(
        "/api/v1/ai/providers",
        json={
            "provider_name": "Mock OpenAI Compatible",
            "base_url": "http://127.0.0.1:9999/v1",
            "model_name": "mock-model",
            "api_key": "sk-test-secret-value",
            "enabled": True,
        },
    )

    assert response.status_code == 201
    payload = response.json()["data"]
    assert "api_key" not in payload
    assert payload["api_key_configured"] is True
    assert payload["api_key_masked"] == "configured"
    assert payload["enabled"] is True

    provider = (
        await db_session.execute(select(AIProviderConfig).where(AIProviderConfig.id == payload["id"]))
    ).scalar_one()
    assert provider.encrypted_api_key != "sk-test-secret-value"
    assert get_secret_cipher(get_settings()).decrypt_secret(provider.encrypted_api_key) == "sk-test-secret-value"


async def test_only_one_provider_can_be_enabled(client: AsyncClient, db_session):
    await _login_user(client, db_session)

    first = await client.post(
        "/api/v1/ai/providers",
        json={
            "provider_name": "First",
            "base_url": "http://127.0.0.1:9999/v1",
            "model_name": "first-model",
            "api_key": "first-secret",
            "enabled": True,
        },
    )
    second = await client.post(
        "/api/v1/ai/providers",
        json={
            "provider_name": "Second",
            "base_url": "http://127.0.0.1:9998/v1",
            "model_name": "second-model",
            "api_key": "second-secret",
            "enabled": True,
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201
    providers = (await client.get("/api/v1/ai/providers")).json()["data"]
    enabled = [provider for provider in providers if provider["enabled"]]
    assert len(enabled) == 1
    assert enabled[0]["provider_name"] == "Second"


async def test_provider_test_saves_status_without_real_ai_call(client: AsyncClient, db_session, monkeypatch):
    await _login_user(client, db_session)
    provider_response = await client.post(
        "/api/v1/ai/providers",
        json={
            "provider_name": "Mock",
            "base_url": "http://127.0.0.1:9999/v1",
            "model_name": "mock-model",
            "api_key": "test-secret",
            "enabled": True,
        },
    )
    provider_id = provider_response.json()["data"]["id"]

    async def fake_call(**kwargs):
        from app.services.ai_gateway import AIChatResult

        assert kwargs["api_key"] == "test-secret"
        return AIChatResult(content="ok", http_status=200, duration_ms=12, input_tokens=3, output_tokens=1)

    monkeypatch.setattr("app.services.ai_gateway.call_openai_chat_completion", fake_call)
    response = await client.post(f"/api/v1/ai/providers/{provider_id}/test")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "succeeded"
    detail = (await client.get(f"/api/v1/ai/providers/{provider_id}")).json()["data"]
    assert detail["last_test_status"] == "succeeded"
