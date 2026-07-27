from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class Stock(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stocks"
    __table_args__ = (
        UniqueConstraint("symbol", name="uq_stocks_symbol"),
        UniqueConstraint("exchange", "code", name="uq_stocks_exchange_code"),
        Index("ix_stocks_symbol", "symbol"),
        Index("ix_stocks_code", "code"),
        Index("ix_stocks_name", "name"),
        Index("ix_stocks_short_name", "short_name"),
        Index("ix_stocks_listing_status", "listing_status"),
        Index("ix_stocks_searchable", "is_searchable"),
    )

    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    exchange: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False, default="A_SHARE")
    board: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    security_type: Mapped[str] = mapped_column(String(32), nullable=False, default="common_stock")
    short_name: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))
    english_name: Mapped[str | None] = mapped_column(String(200))
    listing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    listed_at: Mapped[date | None] = mapped_column(Date)
    delisted_at: Mapped[date | None] = mapped_column(Date)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    pinyin: Mapped[str | None] = mapped_column(String(200))
    pinyin_initials: Mapped[str | None] = mapped_column(String(64))
    source_code: Mapped[str] = mapped_column(String(80), nullable=False, default="development_seed")
    source_record_id: Mapped[str | None] = mapped_column(String(160))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_completeness: Mapped[str] = mapped_column(String(32), nullable=False, default="partial")
    is_searchable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Backward-compatible fields from the first backend phase.
    list_status: Mapped[str] = mapped_column(String(16), nullable=False, default="listed")
    list_date: Mapped[date | None] = mapped_column(Date)
    delist_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    data_source: Mapped[str] = mapped_column(String(64), nullable=False, default="development_seed")

    @property
    def searchable_text(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "code": self.code,
            "name": self.name,
            "short_name": self.short_name,
            "full_name": self.full_name,
            "aliases": self.aliases,
            "pinyin": self.pinyin,
            "pinyin_initials": self.pinyin_initials,
        }
