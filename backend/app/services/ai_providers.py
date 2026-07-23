import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.encryption import get_secret_cipher, masked_secret_display
from app.core.errors import AppError, ErrorCode
from app.core.time import utc_now
from app.core.url_security import validate_ai_base_url
from app.models.ai import AIProviderConfig, AITask, AITaskAttempt
from app.schemas.ai import AIProviderCreate, AIProviderOut, AIProviderTestResult, AIProviderUpdate
from app.services import ai_gateway
from app.services.audit import add_audit_log


def provider_to_out(provider: AIProviderConfig) -> AIProviderOut:
    return AIProviderOut(
        id=provider.id,
        provider_name=provider.provider_name,
        api_style="openai_chat_completions",
        base_url=provider.base_url,
        model_name=provider.model_name,
        enabled=provider.enabled,
        api_key_configured=True,
        api_key_masked=masked_secret_display(configured=True),
        request_timeout_seconds=provider.request_timeout_seconds,
        max_output_tokens=provider.max_output_tokens,
        last_test_status=provider.last_test_status,
        last_tested_at=provider.last_tested_at,
        last_error_code=provider.last_error_code,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


async def list_ai_providers(session: AsyncSession, user_id: uuid.UUID) -> list[AIProviderConfig]:
    result = await session.execute(
        select(AIProviderConfig)
        .where(AIProviderConfig.user_id == user_id)
        .order_by(AIProviderConfig.enabled.desc(), AIProviderConfig.created_at.desc())
    )
    return list(result.scalars().all())


async def get_provider_for_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider_id: uuid.UUID,
) -> AIProviderConfig | None:
    result = await session.execute(
        select(AIProviderConfig).where(
            AIProviderConfig.id == provider_id,
            AIProviderConfig.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_provider_or_404(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider_id: uuid.UUID,
) -> AIProviderConfig:
    provider = await get_provider_for_user(session, user_id=user_id, provider_id=provider_id)
    if not provider:
        raise AppError(ErrorCode.AI_PROVIDER_NOT_FOUND, "AI 供应商配置不存在", status_code=404)
    return provider


async def get_enabled_provider(session: AsyncSession, user_id: uuid.UUID) -> AIProviderConfig | None:
    result = await session.execute(
        select(AIProviderConfig).where(AIProviderConfig.user_id == user_id, AIProviderConfig.enabled.is_(True))
    )
    return result.scalar_one_or_none()


async def _disable_other_enabled(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    keep_provider_id: uuid.UUID | None = None,
) -> None:
    statement = update(AIProviderConfig).where(
        AIProviderConfig.user_id == user_id,
        AIProviderConfig.enabled.is_(True),
    )
    if keep_provider_id:
        statement = statement.where(AIProviderConfig.id != keep_provider_id)
    await session.execute(statement.values(enabled=False))


async def create_ai_provider(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    payload: AIProviderCreate,
    settings: Settings,
    request_id: str | None,
) -> AIProviderConfig:
    validated = validate_ai_base_url(str(payload.base_url), settings)
    cipher = get_secret_cipher(settings)
    if payload.enabled:
        await _disable_other_enabled(session, user_id=user_id)
    provider = AIProviderConfig(
        user_id=user_id,
        provider_name=payload.provider_name.strip(),
        api_style="openai_chat_completions",
        base_url=validated.normalized_url,
        model_name=payload.model_name.strip(),
        encrypted_api_key=cipher.encrypt_secret(payload.api_key),
        enabled=payload.enabled,
        request_timeout_seconds=payload.request_timeout_seconds,
        max_output_tokens=payload.max_output_tokens,
    )
    session.add(provider)
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="ai_provider.create",
        target_type="ai_provider_config",
        target_id=provider.id,
        result="success",
        request_id=request_id,
        metadata={"provider_name": provider.provider_name, "enabled": provider.enabled},
    )
    await session.commit()
    await session.refresh(provider)
    return provider


async def update_ai_provider(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider_id: uuid.UUID,
    payload: AIProviderUpdate,
    settings: Settings,
    request_id: str | None,
) -> AIProviderConfig:
    provider = await get_provider_or_404(session, user_id=user_id, provider_id=provider_id)
    if payload.provider_name is not None:
        provider.provider_name = payload.provider_name.strip()
    if payload.base_url is not None:
        provider.base_url = validate_ai_base_url(str(payload.base_url), settings).normalized_url
    if payload.model_name is not None:
        provider.model_name = payload.model_name.strip()
    if payload.api_key is not None:
        provider.encrypted_api_key = get_secret_cipher(settings).encrypt_secret(payload.api_key)
    if payload.request_timeout_seconds is not None:
        provider.request_timeout_seconds = payload.request_timeout_seconds
    if payload.max_output_tokens is not None:
        provider.max_output_tokens = payload.max_output_tokens
    if payload.enabled is not None:
        if payload.enabled:
            await _disable_other_enabled(session, user_id=user_id, keep_provider_id=provider.id)
        provider.enabled = payload.enabled
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="ai_provider.update",
        target_type="ai_provider_config",
        target_id=provider.id,
        result="success",
        request_id=request_id,
        metadata={"enabled": provider.enabled},
    )
    await session.commit()
    await session.refresh(provider)
    return provider


async def delete_ai_provider(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider_id: uuid.UUID,
    request_id: str | None,
) -> None:
    provider = await get_provider_or_404(session, user_id=user_id, provider_id=provider_id)
    await session.delete(provider)
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="ai_provider.delete",
        target_type="ai_provider_config",
        target_id=provider.id,
        result="success",
        request_id=request_id,
    )
    await session.commit()


async def test_ai_provider(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider_id: uuid.UUID,
    settings: Settings,
    request_id: str | None,
) -> AIProviderTestResult:
    provider = await get_provider_or_404(session, user_id=user_id, provider_id=provider_id)
    now = utc_now()
    task = AITask(
        user_id=user_id,
        task_type="provider_connection_test",
        target_type="ai_provider_config",
        target_id=provider.id,
        provider_config_id=provider.id,
        status="running",
        prompt_version="provider-test-v1",
        schema_version="none",
        created_at=now,
        started_at=now,
    )
    session.add(task)
    await session.flush()
    attempt = AITaskAttempt(
        ai_task_id=task.id,
        attempt_number=1,
        status="running",
        created_at=now,
        attempt_metadata={"request_id": request_id},
    )
    session.add(attempt)
    try:
        api_key = get_secret_cipher(settings).decrypt_secret(provider.encrypted_api_key)
        result = await ai_gateway.call_openai_chat_completion(
            provider=provider,
            api_key=api_key,
            messages=[
                {"role": "system", "content": "You are testing a GeniusTrader AI provider connection."},
                {"role": "user", "content": "Reply with the single word ok."},
            ],
            settings=settings,
            max_tokens=16,
        )
        attempt.status = "succeeded"
        attempt.provider_http_status = result.http_status
        attempt.duration_ms = result.duration_ms
        attempt.input_tokens = result.input_tokens
        attempt.output_tokens = result.output_tokens
        task.status = "succeeded"
        task.completed_at = utc_now()
        provider.last_test_status = "succeeded"
        provider.last_error_code = None
    except AppError as exc:
        attempt.status = "failed"
        attempt.error_code = exc.code.value
        attempt.error_detail_redacted = exc.message
        task.status = "failed"
        task.error_code = exc.code.value
        task.failed_at = utc_now()
        provider.last_test_status = "failed"
        provider.last_error_code = exc.code.value
    provider.last_tested_at = utc_now()
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="ai_provider.test",
        target_type="ai_provider_config",
        target_id=provider.id,
        result=provider.last_test_status or "unknown",
        request_id=request_id,
        metadata={"error_code": provider.last_error_code},
    )
    await session.commit()
    await session.refresh(provider)
    return AIProviderTestResult(
        provider_id=provider.id,
        status=provider.last_test_status or "failed",
        error_code=provider.last_error_code,
        tested_at=provider.last_tested_at or utc_now(),
    )
