from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx

from app.core.errors import AppError, ErrorCode
from app.core.url_security import validate_public_content_url, validate_redirect_url

DEFAULT_PROVIDER_HEADERS = {
    "User-Agent": "GeniusTrader-MVP/0.1 controlled-provider-fetch (+no-cookies; no-js)",
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml,application/pdf;q=0.9,*/*;q=0.8",
}


@dataclass(frozen=True, slots=True)
class ProviderHttpResult:
    url: str
    status_code: int | None
    elapsed_ms: int
    content_type: str | None
    response_bytes: int
    text: str | None
    content: bytes
    error_code: str | None = None

    @property
    def ok(self) -> bool:
        return self.status_code is not None and 200 <= self.status_code < 300 and self.error_code is None


async def provider_http_request(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: int,
    max_bytes: int,
    max_redirects: int = 3,
) -> ProviderHttpResult:
    import time

    current = validate_public_content_url(url).normalized_url
    merged_headers = {**DEFAULT_PROVIDER_HEADERS, **(headers or {})}
    started = time.perf_counter()
    async with httpx.AsyncClient(
        headers=merged_headers,
        timeout=timeout_seconds,
        follow_redirects=False,
    ) as client:
        for redirect_count in range(max_redirects + 1):
            try:
                response_context = client.stream(method, current, params=params, data=data)
                response = await response_context.__aenter__()
            except httpx.TimeoutException:
                return ProviderHttpResult(
                    url=current,
                    status_code=None,
                    elapsed_ms=int((time.perf_counter() - started) * 1000),
                    content_type=None,
                    response_bytes=0,
                    text=None,
                    content=b"",
                    error_code="TIMEOUT",
                )
            except httpx.HTTPError as exc:
                return ProviderHttpResult(
                    url=current,
                    status_code=None,
                    elapsed_ms=int((time.perf_counter() - started) * 1000),
                    content_type=None,
                    response_bytes=0,
                    text=None,
                    content=b"",
                    error_code=exc.__class__.__name__,
                )

            try:
                if response.is_redirect:
                    if redirect_count >= max_redirects:
                        return ProviderHttpResult(
                            url=current,
                            status_code=response.status_code,
                            elapsed_ms=int((time.perf_counter() - started) * 1000),
                            content_type=response.headers.get("content-type"),
                            response_bytes=0,
                            text=None,
                            content=b"",
                            error_code="TOO_MANY_REDIRECTS",
                        )
                    location = response.headers.get("location")
                    if not location:
                        return ProviderHttpResult(
                            url=current,
                            status_code=response.status_code,
                            elapsed_ms=int((time.perf_counter() - started) * 1000),
                            content_type=response.headers.get("content-type"),
                            response_bytes=0,
                            text=None,
                            content=b"",
                            error_code="REDIRECT_WITHOUT_LOCATION",
                        )
                    current = validate_redirect_url(urljoin(current, location)).normalized_url
                    continue

                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        return ProviderHttpResult(
                            url=str(response.url),
                            status_code=response.status_code,
                            elapsed_ms=int((time.perf_counter() - started) * 1000),
                            content_type=response.headers.get("content-type"),
                            response_bytes=total,
                            text=None,
                            content=b"".join(chunks),
                            error_code="MAX_BYTES_EXCEEDED",
                        )
                    chunks.append(chunk)
                content = b"".join(chunks)
                content_type = response.headers.get("content-type")
                text = _decode_text(content, content_type) if _looks_textual(content_type) else None
                client.cookies.clear()
                return ProviderHttpResult(
                    url=str(response.url),
                    status_code=response.status_code,
                    elapsed_ms=int((time.perf_counter() - started) * 1000),
                    content_type=content_type,
                    response_bytes=len(content),
                    text=text,
                    content=content,
                )
            finally:
                await response_context.__aexit__(None, None, None)
    raise AppError(ErrorCode.ANNOUNCEMENT_SYNC_FAILED, "Provider 请求失败", status_code=502)


def _looks_textual(content_type: str | None) -> bool:
    if not content_type:
        return False
    lowered = content_type.lower()
    return any(value in lowered for value in ("json", "text", "xml", "html"))


def _decode_text(content: bytes, content_type: str | None) -> str:
    encoding = "utf-8"
    if content_type:
        for part in content_type.split(";"):
            part = part.strip()
            if part.lower().startswith("charset="):
                encoding = part.split("=", 1)[1].strip() or "utf-8"
                break
    return content.decode(encoding, errors="replace")

