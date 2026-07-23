from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.url_security import validate_public_content_url, validate_redirect_url


@dataclass(frozen=True)
class FetchResult:
    final_url: str
    status_code: int
    content_type: str
    body_text: str
    response_bytes: int


def _content_type_allowed(content_type: str, settings: Settings) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type in settings.allowed_content_types


def _decode_body(content: bytes, content_type: str) -> str:
    encoding = "utf-8"
    for part in content_type.split(";"):
        part = part.strip()
        if part.lower().startswith("charset="):
            encoding = part.split("=", 1)[1].strip() or "utf-8"
            break
    return content.decode(encoding, errors="replace")


async def fetch_public_content(url: str, settings: Settings) -> FetchResult:
    current = validate_public_content_url(url).normalized_url
    headers = {
        "User-Agent": "GeniusTrader-MVP/0.1 controlled-fetch (+no-cookies; no-js)",
        "Accept": "text/html,text/plain,application/xhtml+xml;q=0.9,*/*;q=0.1",
    }
    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=settings.content_fetch_timeout_seconds,
        headers=headers,
    ) as client:
        for redirect_count in range(settings.content_fetch_max_redirects + 1):
            try:
                response_context = client.stream("GET", current)
                response = await response_context.__aenter__()
            except httpx.TimeoutException as exc:
                raise AppError(ErrorCode.CONTENT_FETCH_TIMEOUT, "内容抓取超时", status_code=504) from exc
            except httpx.HTTPError as exc:
                raise AppError(ErrorCode.CONTENT_FETCH_FAILED, "内容抓取失败", status_code=502) from exc

            try:
                if response.is_redirect:
                    if redirect_count >= settings.content_fetch_max_redirects:
                        raise AppError(ErrorCode.URL_REDIRECT_BLOCKED, "重定向次数超过限制", status_code=422)
                    location = response.headers.get("location")
                    if not location:
                        raise AppError(ErrorCode.URL_REDIRECT_BLOCKED, "重定向缺少目标地址", status_code=422)
                    current = validate_redirect_url(urljoin(current, location)).normalized_url
                    continue

                content_type = response.headers.get("content-type", "").lower()
                if content_type and not _content_type_allowed(content_type, settings):
                    raise AppError(ErrorCode.CONTENT_TYPE_NOT_ALLOWED, "内容类型不在允许范围内", status_code=415)
                if response.status_code >= 400:
                    raise AppError(ErrorCode.CONTENT_FETCH_FAILED, "远程页面返回错误状态", status_code=502)
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > settings.content_fetch_max_bytes:
                        raise AppError(ErrorCode.CONTENT_TOO_LARGE, "内容大小超过抓取限制", status_code=413)
                    chunks.append(chunk)
                content = b"".join(chunks)
                return FetchResult(
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type or "unknown",
                    body_text=_decode_body(content, content_type),
                    response_bytes=len(content),
                )
            finally:
                await response_context.__aexit__(None, None, None)
    raise AppError(ErrorCode.CONTENT_FETCH_FAILED, "内容抓取失败", status_code=502)
