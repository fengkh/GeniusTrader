# ruff: noqa: I001
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.stock import Stock
from app.models.user import User


class WatchlistGroup(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "watchlist_groups"
    __table_args__ = (
        Index("uq_watchlist_groups_user_name", "user_id", "name", unique=True),
        Index(
            "uq_watchlist_groups_one_default",
            "user_id",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
        CheckConstraint("sort_order >= 0", name="watchlist_groups_sort_order_non_negative"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship()


class UserWatchlistItem(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_watchlist_items"
    __table_args__ = (
        Index("ix_user_watchlist_items_user_sort", "user_id", "sort_order", "created_at"),
        Index(
            "uq_user_watchlist_items_active_stock",
            "user_id",
            "stock_id",
            unique=True,
            postgresql_where=text("archived_at IS NULL"),
        ),
        CheckConstraint("sort_order >= 0", name="user_watchlist_items_sort_order_non_negative"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stock_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stocks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("watchlist_groups.id", ondelete="SET NULL"),
    )
    attention_reason: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()
    stock: Mapped[Stock] = relationship()
    group: Mapped[WatchlistGroup | None] = relationship()
