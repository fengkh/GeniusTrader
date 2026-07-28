from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.providers.statuses import ProviderStatus


@dataclass(frozen=True, slots=True)
class MarketDataQuery:
    trade_date: date | None
    date_from: date | None
    date_to: date | None
    symbols: list[str]
    max_records: int
    mode: str = "latest_completed_trade_day"
    dry_run: bool = False


@dataclass(frozen=True, slots=True)
class TradeCalendarDay:
    trade_date: date
    is_open: bool
    previous_open_date: date | None = None
    next_open_date: date | None = None
    source_code: str = "unknown"


@dataclass(frozen=True, slots=True)
class DailyMarketSnapshotRecord:
    source_code: str
    symbol: str
    trade_date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    pre_close: Decimal | None
    change: Decimal | None
    pct_change: Decimal | None
    volume: Decimal | None
    amount: Decimal | None
    turnover_rate: Decimal | None
    volume_ratio: Decimal | None
    total_market_value: Decimal | None
    circulating_market_value: Decimal | None
    pe_ttm: Decimal | None
    pb: Decimal | None
    is_trading: bool | None
    data_completeness: str
    source_updated_at: datetime | None
    fetched_at: datetime
    raw_metadata_hash: str
    limitations: list[str] = field(default_factory=list)
    source_record_ref: str | None = None


@dataclass(frozen=True, slots=True)
class MarketDataProviderResult:
    status: ProviderStatus
    records: list[DailyMarketSnapshotRecord] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
