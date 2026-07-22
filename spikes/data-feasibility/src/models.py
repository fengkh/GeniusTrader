from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal


CapabilityStatus = Literal[
    "PASS",
    "PASS_EMPTY",
    "PERMISSION_DENIED",
    "RATE_LIMITED",
    "API_ERROR",
    "INVALID_REQUEST",
    "SKIPPED_TIME_WINDOW",
    "NOT_SUPPORTED",
    "DATA_INSUFFICIENT",
]

MetricStatus = Literal[
    "PASS",
    "PASS_EMPTY",
    "DATA_INSUFFICIENT",
    "NOT_AVAILABLE_WITH_DAILY_DATA",
    "MISSING_INPUT",
    "API_ERROR",
]


CAPABILITY_STATUSES: set[str] = {
    "PASS",
    "PASS_EMPTY",
    "PERMISSION_DENIED",
    "RATE_LIMITED",
    "API_ERROR",
    "INVALID_REQUEST",
    "SKIPPED_TIME_WINDOW",
    "NOT_SUPPORTED",
    "DATA_INSUFFICIENT",
}


@dataclass(frozen=True)
class CapabilityRecord:
    capability: str
    api_name: str
    status: CapabilityStatus
    queried_at: str
    parameters_summary: dict[str, Any]
    fields_requested: list[str]
    fields_returned: list[str]
    row_count: int
    earliest_date: str | None
    latest_date: str | None
    duration_ms: int
    unit_notes: str
    permission_or_error_message: str | None
    impacts_features: list[str]
    recommended_fallback: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MetricResult:
    symbol: str
    metric: str
    value: float | None
    unit: str
    formula_version: str
    input_data_source: str
    window: str
    as_of_date: str | None
    status: MetricStatus
    missing_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QualityIssue:
    symbol: str
    dataset: str
    check_name: str
    status: Literal["PASS", "WARN", "FAIL"]
    message: str
    affected_dates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SpikeContext:
    provider: str
    queried_at: str
    shanghai_now: str
    latest_trade_date: str | None
    days: int
    percentile_window: int
    symbols: list[str]
    skipped_optional: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_like_iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")
