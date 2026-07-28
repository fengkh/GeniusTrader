import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.stock import Stock

MARKET_DATA_AUTHORIZATION_VALUES = (
    "'unverified', 'personal_development_only', 'commercial_evaluation', "
    "'commercially_authorized', 'prohibited', 'expired'"
)

MARKET_DATA_HEALTH_VALUES = (
    "'unknown', 'pass', 'partial', 'data_insufficient', 'not_available', "
    "'network_error', 'timeout', 'rate_limited', 'access_denied', 'source_changed', "
    "'parse_error', 'content_unavailable', 'legal_hold', 'disabled'"
)


class MarketDataSource(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "market_data_sources"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('official_exchange', 'third_party_data_service', 'development_mock')",
            name="market_data_sources_type_allowed",
        ),
        CheckConstraint(
            f"authorization_status IN ({MARKET_DATA_AUTHORIZATION_VALUES})",
            name="market_data_sources_authorization_allowed",
        ),
        CheckConstraint(
            f"last_health_status IN ({MARKET_DATA_HEALTH_VALUES})",
            name="market_data_sources_health_allowed",
        ),
        Index("uq_market_data_sources_source_code", "source_code", unique=True),
        Index("ix_market_data_sources_production_enabled", "production_enabled"),
    )

    source_code: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_status: Mapped[str] = mapped_column(String(40), nullable=False)
    usage_scope: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    production_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_health_status: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    last_health_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    limitations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class MarketDataSyncRun(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "market_data_sync_runs"
    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('manual_admin', 'cli', 'scheduled', 'dry_run')",
            name="market_data_sync_runs_trigger_allowed",
        ),
        CheckConstraint(
            "status IN ('running', 'complete', 'partial', 'failed', 'data_insufficient', "
            "'not_available', 'network_error', 'timeout', 'rate_limited', 'access_denied', "
            "'source_changed', 'parse_error', 'content_unavailable', 'legal_hold', 'disabled')",
            name="market_data_sync_runs_status_allowed",
        ),
        CheckConstraint(
            "sync_mode IN ('latest_completed_trade_day', 'selected_trade_date', 'optional_backfill')",
            name="market_data_sync_runs_mode_allowed",
        ),
        Index("ix_market_data_sync_runs_source_started", "source_code", "started_at"),
        Index("ix_market_data_sync_runs_requested_date", "requested_trade_date"),
        Index("ix_market_data_sync_runs_resolved_date", "resolved_trade_date"),
        Index(
            "uq_market_data_sync_runs_active_source_date",
            "source_code",
            "resolved_trade_date",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    source_code: Mapped[str] = mapped_column(String(80), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False)
    sync_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_trade_date: Mapped[date | None] = mapped_column(Date)
    resolved_trade_date: Mapped[date | None] = mapped_column(Date)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    requested_symbol_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    received_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_summary: Mapped[str | None] = mapped_column(String(500))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StockDailySnapshot(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stock_daily_snapshots"
    __table_args__ = (
        CheckConstraint(
            "data_completeness IN ('complete', 'usable', 'partial', 'insufficient')",
            name="stock_daily_snapshots_completeness_allowed",
        ),
        UniqueConstraint("stock_id", "trade_date", "source_code", name="uq_stock_daily_snapshots_stock_date_source"),
        Index("ix_stock_daily_snapshots_stock_date", "stock_id", "trade_date"),
        Index("ix_stock_daily_snapshots_source_date", "source_code", "trade_date"),
    )

    stock_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stocks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_code: Mapped[str] = mapped_column(String(80), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pre_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    change: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pct_change: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    turnover_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    volume_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    total_market_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    circulating_market_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    pe_ttm: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pb: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    is_trading: Mapped[bool | None] = mapped_column(Boolean)
    data_completeness: Mapped[str] = mapped_column(String(32), nullable=False)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_metadata_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_record_ref: Mapped[str | None] = mapped_column(Text)

    stock: Mapped[Stock] = relationship()
