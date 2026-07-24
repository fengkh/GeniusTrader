import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class AIProviderConfig(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_provider_configs"
    __table_args__ = (
        CheckConstraint(
            "api_style IN ('openai_chat_completions')",
            name="ai_provider_configs_api_style_allowed",
        ),
        Index(
            "uq_ai_provider_configs_one_enabled",
            "user_id",
            unique=True,
            postgresql_where=text("enabled = true"),
        ),
        Index("ix_ai_provider_configs_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_style: Mapped[str] = mapped_column(String(50), nullable=False, default="openai_chat_completions")
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    request_timeout_seconds: Mapped[int | None] = mapped_column(Integer)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    extra_headers_encrypted: Mapped[str | None] = mapped_column(Text)
    last_test_status: Mapped[str | None] = mapped_column(String(50))
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))


class AITask(UuidPrimaryKeyMixin, Base):
    __tablename__ = "ai_tasks"
    __table_args__ = (
        CheckConstraint(
            "task_type IN ('provider_connection_test', 'information_sentiment_analysis', "
            "'user_daily_review_generation')",
            name="ai_tasks_task_type_allowed",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="ai_tasks_status_allowed",
        ),
        Index("ix_ai_tasks_user_status", "user_id", "status"),
        Index("ix_ai_tasks_target", "target_type", "target_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_provider_configs.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    input_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))


class AITaskAttempt(UuidPrimaryKeyMixin, Base):
    __tablename__ = "ai_task_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="ai_task_attempts_status_allowed",
        ),
        Index("ix_ai_task_attempts_task_number", "ai_task_id", "attempt_number", unique=True),
    )

    ai_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_http_status: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail_redacted: Mapped[str | None] = mapped_column(Text)
    attempt_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
