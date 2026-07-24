from __future__ import annotations


def stability_summary(results: list[dict]) -> dict[str, int]:
    return {
        "request_count": sum(int(result.get("request_count") or 0) for result in results),
        "success_count": sum(int(result.get("success_count") or 0) for result in results),
        "failure_count": sum(int(result.get("failure_count") or 0) for result in results),
        "rate_limited_count": sum(1 for result in results if result.get("status") == "RATE_LIMITED"),
        "access_denied_count": sum(1 for result in results if result.get("status") == "ACCESS_DENIED"),
        "timeout_count": sum(1 for result in results if result.get("status") == "TIMEOUT"),
    }
