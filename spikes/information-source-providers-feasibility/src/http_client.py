from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

from .rate_limit import RateLimiter
from .url_utils import assert_public_url


DEFAULT_HEADERS = {
    "User-Agent": "GeniusTraderProviderSpike/0.1 (+https://github.com/fengkh/GeniusTrader)",
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml,application/pdf;q=0.9,*/*;q=0.8",
}


@dataclass(slots=True)
class HttpResult:
    url: str
    status_code: int | None
    elapsed_ms: int
    content_type: str | None
    content_length: int | None
    text: str | None
    content: bytes
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status_code is not None and 200 <= self.status_code < 300 and self.error is None


class SpikeHttpClient:
    def __init__(self, *, timeout: float = 10, max_bytes: int = 2_000_000, delay_seconds: float = 1.0) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.rate_limiter = RateLimiter(delay_seconds)
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.request_count = 0

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> HttpResult:
        return self._request("GET", url, headers=headers)

    def post(self, url: str, *, data: dict[str, Any] | None = None, json_body: Any = None, headers: dict[str, str] | None = None) -> HttpResult:
        return self._request("POST", url, data=data, json_body=json_body, headers=headers)

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, Any] | None = None,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> HttpResult:
        assert_public_url(url)
        self.rate_limiter.wait()
        self.request_count += 1
        started = time.perf_counter()
        try:
            response = self.session.request(
                method,
                url,
                data=data,
                json=json_body,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=True,
                stream=True,
            )
            self.session.cookies.clear()
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > self.max_bytes:
                    return HttpResult(
                        url=response.url,
                        status_code=response.status_code,
                        elapsed_ms=int((time.perf_counter() - started) * 1000),
                        content_type=response.headers.get("Content-Type"),
                        content_length=total,
                        text=None,
                        content=b"".join(chunks),
                        error="MAX_BYTES_EXCEEDED",
                    )
                chunks.append(chunk)
            content = b"".join(chunks)
            text = None
            content_type = response.headers.get("Content-Type")
            if content_type and ("text" in content_type or "json" in content_type or "xml" in content_type):
                response._content = content
                if not response.encoding or response.encoding.lower() in {"iso-8859-1", "latin-1"}:
                    response.encoding = response.apparent_encoding or "utf-8"
                text = response.text
            return HttpResult(
                url=response.url,
                status_code=response.status_code,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                content_type=content_type,
                content_length=len(content),
                text=text,
                content=content,
            )
        except requests.Timeout:
            return HttpResult(url=url, status_code=None, elapsed_ms=int((time.perf_counter() - started) * 1000), content_type=None, content_length=None, text=None, content=b"", error="TIMEOUT")
        except requests.RequestException as exc:
            return HttpResult(url=url, status_code=None, elapsed_ms=int((time.perf_counter() - started) * 1000), content_type=None, content_length=None, text=None, content=b"", error=exc.__class__.__name__)
