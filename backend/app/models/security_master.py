import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.stock import Stock
from app.models.user import User

SECURITY_MASTER_SYNC_STATUS_VALUES = (
    "'running', 'complete', 'partial', 'failed', 'data_insufficient', 'not_available', "
    "'network_error', 'timeout', 'rate_limited', 'access_denied', 'source_changed', "
    "'parse_error', 'content_unavailable', 'legal_hold', 'disabled'"
)


class SecurityMasterSyncRun(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "security_master_sync_runs"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({SECURITY_MASTER_SYNC_STATUS_VALUES})",
            name="security_master_sync_runs_status_allowed",
        ),
        CheckConstraint("request_count >= 0", name="security_master_sync_runs_request_count_non_negative"),
        CheckConstraint("received_count >= 0", name="security_master_sync_runs_received_count_non_negative"),
        CheckConstraint("created_count >= 0", name="security_master_sync_runs_created_count_non_negative"),
        CheckConstraint("updated_count >= 0", name="security_master_sync_runs_updated_count_non_negative"),
        CheckConstraint("unchanged_count >= 0", name="security_master_sync_runs_unchanged_count_non_negative"),
        CheckConstraint("deactivated_count >= 0", name="security_master_sync_runs_deactivated_count_non_negative"),
        CheckConstraint("failure_count >= 0", name="security_master_sync_runs_failure_count_non_negative"),
        Index("ix_security_master_sync_runs_source_started", "source_code", "started_at"),
        Index("ix_security_master_sync_runs_triggered", "triggered_by_user_id", "started_at"),
    )

    triggered_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_code: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    exchanges: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    received_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deactivated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_summary: Mapped[str | None] = mapped_column(String(500))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    triggered_by_user: Mapped[User] = relationship()


class SecuritySourceRecord(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "security_source_records"
    __table_args__ = (
        Index("uq_security_source_records_provider_id", "source_code", "provider_security_id", unique=True),
        Index("ix_security_source_records_stock", "stock_id"),
        Index("ix_security_source_records_source_status", "source_code", "source_status"),
    )

    stock_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_code: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_security_id: Mapped[str] = mapped_column(String(160), nullable=False)
    source_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(200))
    raw_metadata_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_status: Mapped[str] = mapped_column(String(40), nullable=False)

    stock: Mapped[Stock] = relationship()
