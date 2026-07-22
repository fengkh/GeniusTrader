from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

CapabilityStatus = Literal[
    "PASS",
    "PASS_EMPTY",
    "PARTIAL_PASS",
    "NOT_SUPPORTED",
    "NETWORK_ERROR",
    "UPSTREAM_ERROR",
    "SOURCE_CHANGED",
    "RATE_LIMITED",
    "INVALID_REQUEST",
    "SCHEMA_MISMATCH",
    "UNIT_UNCERTAIN",
    "DATA_INSUFFICIENT",
    "SKIPPED_TIME_WINDOW",
]

MetricStatus = Literal[
    "PASS",
    "PASS_EMPTY",
    "DATA_INSUFFICIENT",
    "NOT_AVAILABLE_WITH_DAILY_DATA",
    "UPSTREAM_ERROR",
    "UNIT_UNCERTAIN",
]

CAPABILITY_STATUSES: set[str] = {
    "PASS",
    "PASS_EMPTY",
    "PARTIAL_PASS",
    "NOT_SUPPORTED",
    "NETWORK_ERROR",
    "UPSTREAM_ERROR",
    "SOURCE_CHANGED",
    "RATE_LIMITED",
    "INVALID_REQUEST",
    "SCHEMA_MISMATCH",
    "UNIT_UNCERTAIN",
    "DATA_INSUFFICIENT",
    "SKIPPED_TIME_WINDOW",
}

INTERNAL_STOCK_BASIC_FIELDS = [
    "symbol",
    "provider_symbol",
    "name",
    "exchange",
    "market",
    "list_status",
    "list_date",
    "delist_date",
    "currency",
    "provider",
    "fetched_at",
]

INTERNAL_SNAPSHOT_FIELDS = [
    "symbol",
    "trade_date",
    "quote_time",
    "open",
    "high",
    "low",
    "close",
    "pre_close",
    "change",
    "pct_change",
    "volume",
    "amount",
    "turnover_rate",
    "volume_ratio",
    "total_market_value",
    "circulating_market_value",
    "trade_status",
    "provider",
    "fetched_at",
]

INTERNAL_DAILY_FIELDS = [
    "symbol",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "pre_close",
    "volume",
    "amount",
    "turnover_rate",
    "amplitude",
    "pct_change",
    "adjustment",
    "provider",
]

INTERNAL_MINUTE_FIELDS = [
    "symbol",
    "datetime",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "provider",
]

INTERNAL_BOARD_FIELDS = [
    "board_id",
    "board_name",
    "board_type",
    "source_system",
    "symbol",
    "effective_date",
    "provider",
]


@dataclass(frozen=True)
class CapabilityRecord:
    provider: str
    provider_version: str
    capability: str
    api_name: str
    status: CapabilityStatus
    queried_at: str
    parameters_summary: dict[str, Any]
    fields_expected: list[str]
    fields_returned: list[str]
    row_count: int
    earliest_date: str | None
    latest_date: str | None
    duration_ms: int
    source_type: str
    original_units: dict[str, str]
    normalized_units: dict[str, str]
    error_message: str | None
    impacts_features: list[str]
    recommended_fallback: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderResult:
    data: Any
    record: CapabilityRecord


@dataclass(frozen=True)
class MetricResult:
    provider: str
    symbol: str
    metric: str
    value: float | None
    unit: str
    formula_version: str
    input_sources: list[str]
    window: str
    as_of_date: str | None
    status: MetricStatus
    missing_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QualityIssue:
    provider: str
    symbol: str
    dataset: str
    check_name: str
    status: Literal["PASS", "WARN", "FAIL"]
    message: str
    affected_dates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ComparisonFieldResult:
    symbol: str
    provider_a: str
    provider_b: str
    field: str
    compared_rows: int
    exact_match_rows: int
    within_tolerance_rows: int
    mismatch_rows: int
    max_absolute_difference: float | None
    max_relative_difference: float | None
    mismatch_examples: list[dict[str, Any]]
    likely_reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StabilityRunResult:
    provider: str
    capability: str
    api_name: str
    run_index: int
    status: CapabilityStatus
    row_count: int
    fields_returned: list[str]
    latest_date: str | None
    duration_ms: int
    error_message: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunManifest:
    generated_at: str
    timezone: str
    python_version: str
    providers_requested: list[str]
    symbols_requested: list[str]
    days: int
    percentile_window: int
    request_interval: float
    stability_runs: int
    skipped: dict[str, bool]
    package_versions: dict[str, str]
    api_signatures: dict[str, dict[str, str]]
    documentation_sources: list[dict[str, str]]
    legal_boundary: str = (
        "Library licenses and public package availability do not grant data redistribution or "
        "commercial data usage rights. LEGAL_REVIEW_REQUIRED before commercialization."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
