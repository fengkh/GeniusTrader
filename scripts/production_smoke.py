#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


SENSITIVE_MARKERS = (
    "APP_ENCRYPTION_KEYS",
    "DATABASE_URL",
    "password",
    "api_key",
    "authorization",
    "cookie",
    "csrf",
    "token",
    "traceback",
)


@dataclass
class SmokeResult:
    name: str
    status: str
    message: str
    details: dict[str, object] | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "details": self.details or {},
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GeniusTrader production HTTP smoke checks")
    parser.add_argument("--base-url", required=True, help="Production base URL, e.g. https://example.com")
    parser.add_argument("--admin-email", help="Optional operator label only; no password or token arguments are accepted")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    results = run_smoke(args.base_url.rstrip("/") + "/", timeout=args.timeout)
    status = "fail" if any(item.status == "fail" for item in results) else "warning" if any(
        item.status == "warning" for item in results
    ) else "pass"
    print(
        json.dumps(
            {
                "status": status,
                "base_url": args.base_url,
                "admin_email_configured": bool(args.admin_email),
                "results": [item.as_dict() for item in results],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    raise SystemExit(1 if status == "fail" else 2 if status == "warning" else 0)


def run_smoke(base_url: str, *, timeout: float) -> list[SmokeResult]:
    results: list[SmokeResult] = []
    results.append(_expect_success("frontend_home", base_url, "", timeout=timeout))
    results.append(_expect_success("health_live", base_url, "api/v1/health/live", timeout=timeout))
    results.append(_expect_success("health_ready", base_url, "api/v1/health/ready", timeout=timeout))
    results.append(_expect_success("openapi", base_url, "openapi.json", timeout=timeout))
    results.append(_expect_success("login_page", base_url, "login", timeout=timeout))
    results.append(_expect_rejected_or_missing("public_registration_off", base_url, "api/v1/auth/register", timeout=timeout))
    results.append(_expect_rejected_or_missing("private_api_unauth_rejected", base_url, "api/v1/watchlist", timeout=timeout))
    results.append(_expect_no_sensitive_payload("market_data_status_no_secret_leak", base_url, "api/v1/market-data/status", timeout=timeout))
    results.append(_expect_no_sensitive_payload("security_master_status_no_secret_leak", base_url, "api/v1/security-master/status", timeout=timeout))
    results.append(_expect_no_stack("error_response_no_stack", base_url, "api/v1/__not_found__", timeout=timeout))
    results.append(_security_headers("security_headers", base_url, "api/v1/health/live", timeout=timeout))
    return results


def _request(base_url: str, path: str, *, timeout: float) -> tuple[int, str, dict[str, str]]:
    url = urljoin(base_url, path)
    request = Request(url, headers={"User-Agent": "GeniusTraderProductionSmoke/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read(200_000).decode("utf-8", errors="replace"), dict(response.headers)
    except HTTPError as exc:
        return exc.code, exc.read(200_000).decode("utf-8", errors="replace"), dict(exc.headers)
    except URLError as exc:
        return 0, str(exc.reason), {}


def _expect_success(name: str, base_url: str, path: str, *, timeout: float) -> SmokeResult:
    status, body, _headers = _request(base_url, path, timeout=timeout)
    if 200 <= status < 400:
        return SmokeResult(name, "pass", "请求成功。", {"http_status": status})
    return SmokeResult(name, "fail", "请求失败。", {"http_status": status, "body_sample": _safe_sample(body)})


def _expect_rejected_or_missing(name: str, base_url: str, path: str, *, timeout: float) -> SmokeResult:
    status, body, _headers = _request(base_url, path, timeout=timeout)
    if status in {401, 403, 404, 405}:
        return SmokeResult(name, "pass", "接口未公开或未授权访问被拒绝。", {"http_status": status})
    return SmokeResult(name, "fail", "接口不应对未认证用户成功开放。", {"http_status": status, "body_sample": _safe_sample(body)})


def _expect_no_sensitive_payload(name: str, base_url: str, path: str, *, timeout: float) -> SmokeResult:
    status, body, _headers = _request(base_url, path, timeout=timeout)
    lowered = body.lower()
    if any(marker.lower() in lowered for marker in SENSITIVE_MARKERS):
        return SmokeResult(name, "fail", "响应可能包含敏感字段或栈信息。", {"http_status": status})
    if status in {200, 401, 403}:
        return SmokeResult(name, "pass", "响应未发现敏感字段。", {"http_status": status})
    return SmokeResult(name, "warning", "接口状态非预期，但未发现敏感字段。", {"http_status": status})


def _expect_no_stack(name: str, base_url: str, path: str, *, timeout: float) -> SmokeResult:
    status, body, _headers = _request(base_url, path, timeout=timeout)
    lowered = body.lower()
    if "traceback" in lowered or "stack" in lowered:
        return SmokeResult(name, "fail", "错误响应暴露了栈信息。", {"http_status": status})
    return SmokeResult(name, "pass", "错误响应未暴露栈信息。", {"http_status": status})


def _security_headers(name: str, base_url: str, path: str, *, timeout: float) -> SmokeResult:
    status, _body, headers = _request(base_url, path, timeout=timeout)
    normalized = {key.lower(): value for key, value in headers.items()}
    required = ["x-content-type-options", "x-frame-options", "referrer-policy", "permissions-policy"]
    missing = [key for key in required if key not in normalized]
    if missing:
        return SmokeResult(name, "fail", "缺少基础安全响应头。", {"http_status": status, "missing": missing})
    return SmokeResult(name, "pass", "基础安全响应头存在。", {"http_status": status})


def _safe_sample(value: str) -> str:
    sample = value[:300]
    for marker in SENSITIVE_MARKERS:
        sample = sample.replace(marker, "[redacted]")
        sample = sample.replace(marker.upper(), "[redacted]")
    return sample


if __name__ == "__main__":
    main()
