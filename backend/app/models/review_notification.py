import uuid
from datetime import date, datetime, time
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
    String,
    Text,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class DailyReview(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_reviews"
    __table_args__ = (
        CheckConstraint(
            "status IN ('complete', 'partial', 'empty', 'failed', 'stale')",
            name="daily_reviews_status_allowed",
        ),
        Index("uq_daily_reviews_user_date", "user_id", "review_date", unique=True),
        Index("ix_daily_reviews_user_status", "user_id", "status"),
        Index("ix_daily_reviews_user_generated", "user_id", "generated_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    review_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "daily_review_versions.id",
            ondelete="SET NULL",
            name="fk_daily_reviews_current_version_id_daily_review_versions",
            use_alter=True,
        ),
    )
    input_fingerprint: Mapped[str | None] = mapped_column(String(64))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stale_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DailyReviewVersion(UuidPrimaryKeyMixin, Base):
    __tablename__ = "daily_review_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('complete', 'partial', 'empty', 'failed', 'stale')",
            name="daily_review_versions_status_allowed",
        ),
        CheckConstraint(
            "generation_mode IN ('rules_only', 'rules_and_ai', 'rules_with_ai_fallback')",
            name="daily_review_versions_generation_mode_allowed",
        ),
        Index(
            "ix_daily_review_versions_review_version",
            "daily_review_id",
            "version_number",
            unique=True,
        ),
        Index("ix_daily_review_versions_ai_task", "ai_task_id"),
    )

    daily_review_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("daily_reviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    generation_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    ai_task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_tasks.id", ondelete="SET NULL"),
    )
    rule_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    ai_structured_result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ai_narrative: Mapped[str | None] = mapped_column(Text)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_provider_configs.id", ondelete="SET NULL"),
    )
    model_name: Mapped[str | None] = mapped_column(String(120))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DailyReviewItem(UuidPrimaryKeyMixin, Base):
    __tablename__ = "daily_review_items"
    __table_args__ = (
        CheckConstraint(
            "inclusion_type IN ('analyzed', 'pending_analysis', 'analysis_failed', "
            "'content_insufficient', 'unconfirmed_relation')",
            name="daily_review_items_inclusion_type_allowed",
        ),
        CheckConstraint(
            "relation_scope IN ('watchlist_stock', 'confirmed_non_watchlist_stock', "
            "'unassigned', 'entity_only')",
            name="daily_review_items_relation_scope_allowed",
        ),
        Index(
            "ix_daily_review_items_version_item",
            "daily_review_version_id",
            "information_item_id",
            unique=True,
        ),
        Index("ix_daily_review_items_information", "information_item_id"),
        Index("ix_daily_review_items_effective_date", "effective_date"),
    )

    daily_review_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("daily_review_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    information_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("information_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    analysis_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("information_analysis_versions.id", ondelete="SET NULL"),
    )
    information_content_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("information_contents.id", ondelete="SET NULL"),
    )
    inclusion_type: Mapped[str] = mapped_column(String(32), nullable=False)
    inclusion_reason: Mapped[str] = mapped_column(String(300), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    relation_scope: Mapped[str] = mapped_column(String(40), nullable=False)
    relation_status_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_watchlist_related: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BusinessEvent(UuidPrimaryKeyMixin, Base):
    __tablename__ = "business_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('user_daily_review.generated', 'user_daily_review.partial', "
            "'user_daily_review.failed', 'user_daily_review.became_stale', "
            "'information.high_priority_detected', 'information.verification_required', "
            "'ai_task.failed')",
            name="business_events_event_type_allowed",
        ),
        CheckConstraint("severity IN ('info', 'notice', 'important')", name="business_events_severity_allowed"),
        Index("uq_business_events_idempotency_key", "idempotency_key", unique=True),
        Index("ix_business_events_user_created", "user_id", "created_at"),
        Index("ix_business_events_user_type", "user_id", "event_type"),
        Index("ix_business_events_subject", "subject_type", "subject_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    event_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(120))
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Notification(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("severity IN ('info', 'notice', 'important')", name="notifications_severity_allowed"),
        CheckConstraint(
            "status IN ('unread', 'read', 'archived', 'expired')",
            name="notifications_status_allowed",
        ),
        Index("uq_notifications_user_event", "user_id", "event_id", unique=True),
        Index("ix_notifications_user_status_created", "user_id", "status", "created_at"),
        Index("ix_notifications_user_event_type", "user_id", "event_type"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("business_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    deep_link: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationPreference(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        CheckConstraint("channel IN ('in_app')", name="notification_preferences_channel_allowed"),
        CheckConstraint(
            "frequency IN ('immediate', 'daily_digest', 'disabled')",
            name="notification_preferences_frequency_allowed",
        ),
        CheckConstraint(
            "minimum_severity IN ('info', 'notice', 'important')",
            name="notification_preferences_minimum_severity_allowed",
        ),
        Index("uq_notification_preferences_user_event_channel", "user_id", "event_type", "channel", unique=True),
        Index("ix_notification_preferences_user", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    frequency: Mapped[str] = mapped_column(String(32), nullable=False)
    minimum_severity: Mapped[str] = mapped_column(String(32), nullable=False)
    quiet_hours_start: Mapped[time | None] = mapped_column(Time)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")


class NotificationDelivery(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        CheckConstraint("channel IN ('in_app')", name="notification_deliveries_channel_allowed"),
        CheckConstraint(
            "status IN ('pending', 'delivered', 'skipped', 'failed')",
            name="notification_deliveries_status_allowed",
        ),
        Index("uq_notification_deliveries_deduplication", "deduplication_key", unique=True),
        Index("ix_notification_deliveries_user_status", "user_id", "status"),
        Index("ix_notification_deliveries_notification", "notification_id"),
    )

    notification_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    deduplication_key: Mapped[str] = mapped_column(String(200), nullable=False)
