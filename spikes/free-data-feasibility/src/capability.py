from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from .models import CapabilityRecord, CapabilityStatus

DATE_COLUMNS = ["trade_date", "date", "cal_date", "datetime", "quote_time", "time", "effective_date"]


def now_shanghai() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def redact_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    text = re.sub(r"(?i)(token|api_key|apikey|password|secret|cookie)=([^&\s]+)", "[REDACTED_CREDENTIAL]", text)
    text = re.sub(r"\b[A-Za-z0-9_\-]{28,}\b", "[REDACTED_LONG_VALUE]", text)
    return text[:800]


def classify_exception(error: Exception) -> CapabilityStatus:
    message = (redact_text(error) or "").lower()
    network_markers = ["timeout", "timed out", "connection", "network", "dns", "proxy", "ssl", "reset", "refused"]
    rate_markers = ["rate", "too many", "limit", "limited", "频率", "限制", "访问过于频繁"]
    invalid_markers = ["invalid", "bad request", "parameter", "argument", "参数", "字段"]
    source_changed_markers = ["has no attribute", "not found", "no such", "missing", "不存在"]
    if any(marker in message for marker in rate_markers):
        return "RATE_LIMITED"
    if any(marker in message for marker in network_markers):
        return "NETWORK_ERROR"
    if any(marker in message for marker in invalid_markers):
        return "INVALID_REQUEST"
    if any(marker in message for marker in source_changed_markers):
        return "SOURCE_CHANGED"
    return "UPSTREAM_ERROR"


def date_bounds(frame: pd.DataFrame) -> tuple[str | None, str | None]:
    if frame.empty:
        return None, None
    for column in DATE_COLUMNS:
        if column in frame.columns:
            values = frame[column].dropna().astype(str)
            if not values.empty:
                return values.min(), values.max()
    return None, None


def safe_fields(fields: list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    if not fields:
        return []
    return [str(item) for item in fields]


def capability_record_from_frame(
    *,
    provider: str,
    provider_version: str,
    capability: str,
    api_name: str,
    frame: pd.DataFrame,
    queried_at: str,
    parameters_summary: dict[str, Any],
    fields_expected: list[str] | None,
    duration_ms: int,
    source_type: str,
    original_units: dict[str, str] | None,
    normalized_units: dict[str, str] | None,
    impacts_features: list[str],
    recommended_fallback: str,
    status: CapabilityStatus | None = None,
    error_message: str | None = None,
    fields_returned: list[str] | None = None,
) -> CapabilityRecord:
    earliest, latest = date_bounds(frame)
    resolved_status: CapabilityStatus = status or ("PASS" if len(frame) > 0 else "PASS_EMPTY")
    return CapabilityRecord(
        provider=provider,
        provider_version=provider_version,
        capability=capability,
        api_name=api_name,
        status=resolved_status,
        queried_at=queried_at,
        parameters_summary=_safe_parameters(parameters_summary),
        fields_expected=safe_fields(fields_expected),
        fields_returned=fields_returned or list(map(str, frame.columns)),
        row_count=int(len(frame)),
        earliest_date=earliest,
        latest_date=latest,
        duration_ms=duration_ms,
        source_type=source_type,
        original_units=original_units or {},
        normalized_units=normalized_units or {},
        error_message=redact_text(error_message),
        impacts_features=impacts_features,
        recommended_fallback=recommended_fallback,
    )


def synthetic_record(
    *,
    provider: str,
    provider_version: str,
    capability: str,
    api_name: str,
    status: CapabilityStatus,
    queried_at: str | None = None,
    parameters_summary: dict[str, Any] | None = None,
    fields_expected: list[str] | None = None,
    fields_returned: list[str] | None = None,
    source_type: str = "public_library",
    original_units: dict[str, str] | None = None,
    normalized_units: dict[str, str] | None = None,
    error_message: str | None = None,
    impacts_features: list[str] | None = None,
    recommended_fallback: str = "",
) -> CapabilityRecord:
    return CapabilityRecord(
        provider=provider,
        provider_version=provider_version,
        capability=capability,
        api_name=api_name,
        status=status,
        queried_at=queried_at or now_shanghai(),
        parameters_summary=_safe_parameters(parameters_summary or {}),
        fields_expected=safe_fields(fields_expected),
        fields_returned=safe_fields(fields_returned),
        row_count=0,
        earliest_date=None,
        latest_date=None,
        duration_ms=0,
        source_type=source_type,
        original_units=original_units or {},
        normalized_units=normalized_units or {},
        error_message=redact_text(error_message),
        impacts_features=impacts_features or [],
        recommended_fallback=recommended_fallback,
    )


def schema_status(frame: pd.DataFrame, required_fields: list[str]) -> tuple[CapabilityStatus | None, str | None]:
    missing = [field for field in required_fields if field not in frame.columns]
    if missing:
        return "SCHEMA_MISMATCH", f"missing expected fields: {', '.join(missing)}"
    return None, None


def timed_dataframe_call(function: Callable[[], pd.DataFrame], *, retries: int = 1, interval: float = 0.0) -> tuple[pd.DataFrame, int, Exception | None]:
    total_start = time.perf_counter()
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            result = function()
            duration_ms = int((time.perf_counter() - total_start) * 1000)
            if result is None:
                result = pd.DataFrame()
            if not isinstance(result, pd.DataFrame):
                result = pd.DataFrame(result)
            return result, duration_ms, None
        except Exception as error:  # noqa: BLE001 - normalized into provider capability status
            last_error = error
            if classify_exception(error) != "NETWORK_ERROR" or attempt >= retries:
                break
            time.sleep(interval * (2**attempt))
    duration_ms = int((time.perf_counter() - total_start) * 1000)
    return pd.DataFrame(), duration_ms, last_error


def _safe_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in parameters.items():
        lowered = key.lower()
        if any(marker in lowered for marker in ["token", "api", "key", "secret", "password", "cookie"]):
            safe[key] = "[REDACTED]"
        elif isinstance(value, (list, tuple, set)):
            safe[key] = [redact_text(item) for item in value]
        else:
            safe[key] = redact_text(value) if isinstance(value, str) else value
    return safe
