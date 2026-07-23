from datetime import date

from sqlalchemy import Date, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class Stock(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stocks"
    __table_args__ = (
        UniqueConstraint("symbol", "exchange", name="uq_stocks_symbol_exchange"),
        Index("ix_stocks_symbol", "symbol"),
        Index("ix_stocks_name", "name"),
    )

    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    exchange: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False, default="A_SHARE")
    list_status: Mapped[str] = mapped_column(String(16), nullable=False, default="listed")
    list_date: Mapped[date | None] = mapped_column(Date)
    delist_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    data_source: Mapped[str] = mapped_column(String(64), nullable=False, default="development_seed")
