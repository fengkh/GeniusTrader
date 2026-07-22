from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pandas as pd

from .models import CapabilityRecord, CapabilityStatus

DATE_COLUMNS = [
    "trade_date",
    "cal_date",
    "ann_date",
    "suspend_date",
    "resume_date",
    "list_date",
    "delist_date",
    "datetime",
    "time",
]


def redact_text(value: Any, token: str | None = None) -> str | None:
    if value is None:
        return None

    text = str(value)
    if token:
        text = text.replace(token, "[REDACTED_TOKEN]")

    text = re.sub(r"(?i)(token|api_key|apikey|password|secret)=([^&\s]+)", r"\1=[REDACTED]", text)
    text = re.sub(r"\b[A-Za-z0-9_\-]{28,}\b", "[REDACTED_LONG_VALUE]", text)
    return text[:500]


def normalize_exception(error: Exception, token: str | None = None) -> tuple[CapabilityStatus, str]:
    message = redact_text(error, token) or ""
    lowered = message.lower()

    permission_markers = [
        "permission",
        "not allowed",
        "没有访问",
        "权限",
        "积分",
        "无权限",
        "forbidden",
    ]
    rate_markers = ["rate", "频率", "每分钟", "访问太频繁", "limit"]
    invalid_markers = ["invalid", "参数", "字段", "field", "不存在", "bad request"]

    if any(marker in lowered for marker in rate_markers):
        return "RATE_LIMITED", message
    if any(marker in lowered for marker in permission_markers):
        return "PERMISSION_DENIED", message
    if any(marker in lowered for marker in invalid_markers):
        return "INVALID_REQUEST", message
    return "API_ERROR", message


def date_bounds(frame: pd.DataFrame) -> tuple[str | None, str | None]:
    for column in DATE_COLUMNS:
        if column in frame.columns and not frame[column].dropna().empty:
            values = frame[column].dropna().astype(str)
            return values.min(), values.max()
    return None, None


def safe_fields(fields: str | list[str] | None) -> list[str]:
    if fields is None:
        return []
    if isinstance(fields, list):
        return fields
    if fields.strip() == "":
        return []
    return [item.strip() for item in fields.split(",") if item.strip()]


def capability_record_from_frame(
    *,
    capability: str,
    api_name: str,
    frame: pd.DataFrame,
    queried_at: str,
    parameters_summary: dict[str, Any],
    fields_requested: str | list[str] | None,
    duration_ms: int,
    unit_notes: str,
    impacts_features: list[str],
    recommended_fallback: str,
) -> CapabilityRecord:
    earliest, latest = date_bounds(frame)
    status: CapabilityStatus = "PASS" if len(frame) > 0 else "PASS_EMPTY"
    return CapabilityRecord(
        capability=capability,
        api_name=api_name,
        status=status,
        queried_at=queried_at,
        parameters_summary=parameters_summary,
        fields_requested=safe_fields(fields_requested),
        fields_returned=list(frame.columns),
        row_count=int(len(frame)),
        earliest_date=earliest,
        latest_date=latest,
        duration_ms=duration_ms,
        unit_notes=unit_notes,
        permission_or_error_message=None,
        impacts_features=impacts_features,
        recommended_fallback=recommended_fallback,
    )


def synthetic_record(
    *,
    capability: str,
    api_name: str,
    status: CapabilityStatus,
    queried_at: str,
    parameters_summary: dict[str, Any],
    fields_requested: str | list[str] | None = None,
    unit_notes: str = "",
    permission_or_error_message: str | None = None,
    impacts_features: list[str] | None = None,
    recommended_fallback: str = "",
) -> CapabilityRecord:
    return CapabilityRecord(
        capability=capability,
        api_name=api_name,
        status=status,
        queried_at=queried_at,
        parameters_summary=parameters_summary,
        fields_requested=safe_fields(fields_requested),
        fields_returned=[],
        row_count=0,
        earliest_date=None,
        latest_date=None,
        duration_ms=0,
        unit_notes=unit_notes,
        permission_or_error_message=permission_or_error_message,
        impacts_features=impacts_features or [],
        recommended_fallback=recommended_fallback,
    )


def timed_call(function: Callable[[], pd.DataFrame]) -> tuple[pd.DataFrame, int]:
    start = time.perf_counter()
    result = function()
    duration_ms = int((time.perf_counter() - start) * 1000)
    if result is None:
        result = pd.DataFrame()
    return result, duration_ms


def now_queried_at() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
