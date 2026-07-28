from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import OrmModel
from app.schemas.stock import StockRead


class MarketDataProviderOut(BaseModel):
    source_code: str
    display_name: str
    implemented: bool
    enabled_by_config: bool
    source_type: str
    authorization_status: str
    usage_scope: list[str]
    production_enabled: bool
    capabilities: list[str]
    limitations: list[str]


class MarketDataSourceOut(OrmModel):
    id: UUID
    source_code: str
    display_name: str
    source_type: str
    authorization_status: str
    usage_scope: list[str]
    production_enabled: bool
    capabilities: list[str]
    last_health_status: str
    last_health_checked_at: datetime | None
    limitations: list[str]
    created_at: datetime
    updated_at: datetime


class MarketDataSyncRunOut(OrmModel):
    id: UUID
    source_code: str
    trigger_type: str
    sync_mode: str
    status: str
    requested_trade_date: date | None
    resolved_trade_date: date | None
    lookback_days: int
    requested_symbol_count: int
    received_count: int
    created_count: int
    updated_count: int
    unchanged_count: int
    failure_count: int
    error_code: str | None
    error_summary: str | None
    metrics: dict
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MarketDataStatusOut(BaseModel):
    sources: list[MarketDataSourceOut]
    providers: list[MarketDataProviderOut]
    latest_trade_date: date | None
    latest_source_code: str | None
    latest_fetched_at: datetime | None
    latest_sync_status: str | None
    latest_sync_run: MarketDataSyncRunOut | None
    production_authorization_pending: bool
    user_notice: str
    data_gaps: list[str]


class StockDailySnapshotOut(OrmModel):
    id: UUID
    stock_id: UUID
    source_code: str
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
    limitations: list[str]
    created_at: datetime
    updated_at: datetime


class StockMarketSnapshotOut(BaseModel):
    stock: StockRead
    snapshot: StockDailySnapshotOut | None
    status: Literal["available", "stale", "partial", "unavailable"]
    latest_completed_trade_date: date | None
    source_code: str | None
    authorization_status: str | None
    production_enabled: bool
    message: str
    unit_notes: dict[str, str]


class WatchlistMarketSnapshotOut(BaseModel):
    watchlist_item_id: UUID
    stock: StockRead
    snapshot: StockDailySnapshotOut | None
    status: Literal["available", "stale", "partial", "unavailable"]
    message: str


class MarketDataSyncRequest(BaseModel):
    source_code: str = Field(default="TUSHARE_PRO", min_length=1, max_length=80)
    sync_mode: Literal["latest_completed_trade_day", "selected_trade_date", "optional_backfill"] = (
        "latest_completed_trade_day"
    )
    trade_date: date | None = None
    lookback_days: int = Field(default=1, ge=1, le=30)
    stock_ids: list[UUID] = Field(default_factory=list)
    use_current_watchlist: bool = True
    dry_run: bool = False
