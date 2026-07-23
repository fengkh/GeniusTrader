import json
import time
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.url_security import validate_ai_base_url
from app.models.ai import AIProviderConfig


@dataclass(frozen=True)
class AIChatResult:
    content: str
    http_status: int
    duration_ms: int
    input_tokens: int | None
    output_tokens: int | None


def _chat_completion_url(base_url: str) -> str:
    base = base_url.rstrip("/") + "/"
    if base.endswith("/chat/completions/"):
        return base.rstrip("/")
    return urljoin(base, "chat/completions")


def _error_from_status(status_code: int) -> ErrorCode:
    if status_code in {401, 403}:
        return ErrorCode.AI_PROVIDER_AUTH_FAILED
    if status_code == 404:
        return ErrorCode.AI_MODEL_NOT_FOUND
    return ErrorCode.AI_PROVIDER_UNAVAILABLE


async def call_openai_chat_completion(
    *,
    provider: AIProviderConfig,
    api_key: str,
    messages: list[dict[str, str]],
    settings: Settings,
    max_tokens: int | None = None,
    response_format: dict[str, str] | None = None,
) -> AIChatResult:
    validated = validate_ai_base_url(provider.base_url, settings)
    timeout = provider.request_timeout_seconds or settings.ai_request_timeout_seconds
    payload = {
        "model": provider.model_name,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens or provider.max_output_tokens or settings.ai_max_output_tokens,
    }
    if response_format is not None:
        payload["response_format"] = response_format
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                _chat_completion_url(validated.normalized_url),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise AppError(ErrorCode.AI_PROVIDER_TIMEOUT, "AI 调用超时", status_code=504) from exc
    except httpx.HTTPError as exc:
        raise AppError(ErrorCode.AI_PROVIDER_UNAVAILABLE, "AI 服务暂不可用", status_code=502) from exc

    duration_ms = round((time.perf_counter() - started) * 1000)
    if response.status_code >= 400:
        code = _error_from_status(response.status_code)
        raise AppError(code, "AI 服务返回错误", status_code=502, details={"provider_http_status": response.status_code})
    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise AppError(ErrorCode.AI_INVALID_RESPONSE, "AI 返回格式无效", status_code=502) from exc
    usage = data.get("usage") if isinstance(data, dict) else {}
    return AIChatResult(
        content=str(content),
        http_status=response.status_code,
        duration_ms=duration_ms,
        input_tokens=usage.get("prompt_tokens") if isinstance(usage, dict) else None,
        output_tokens=usage.get("completion_tokens") if isinstance(usage, dict) else None,
    )
