import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class InformationItem(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "information_items"
    __table_args__ = (
        CheckConstraint(
            "input_type IN ('manual_text', 'public_url')",
            name="information_items_input_type_allowed",
        ),
        CheckConstraint(
            "status IN ('submitted', 'fetching', 'fetch_failed', 'ready', 'analyzing', "
            "'analyzed', 'analysis_failed', 'archived')",
            name="information_items_status_allowed",
        ),
        CheckConstraint(
            "source_type IN ('announcement', 'news', 'social', 'analyst_opinion', "
            "'user_note', 'unknown')",
            name="information_items_source_type_allowed",
        ),
        Index("ix_information_items_user_status", "user_id", "status"),
        Index("ix_information_items_user_created", "user_id", "created_at"),
        Index("ix_information_items_user_source", "user_id", "source_type"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    input_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    title: Mapped[str | None] = mapped_column(String(300))
    user_note: Mapped[str | None] = mapped_column(Text)
    is_important: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InformationSource(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "information_sources"
    __table_args__ = (
        CheckConstraint(
            "fetch_status IN ('pending', 'succeeded', 'failed', 'skipped')",
            name="information_sources_fetch_status_allowed",
        ),
        Index("ix_information_sources_item_id", "information_item_id"),
        Index("ix_information_sources_user_url_hash", "user_id", "url_hash", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    information_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("information_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_url: Mapped[str | None] = mapped_column(Text)
    normalized_url: Mapped[str | None] = mapped_column(Text)
    url_hash: Mapped[str | None] = mapped_column(String(64))
    source_name: Mapped[str | None] = mapped_column(String(200))
    author: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(120))
    fetch_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")


class InformationContent(UuidPrimaryKeyMixin, Base):
    __tablename__ = "information_contents"
    __table_args__ = (
        CheckConstraint(
            "content_origin IN ('user_input', 'fetched_page', 'user_correction', 'provider_document')",
            name="information_contents_origin_allowed",
        ),
        CheckConstraint(
            "extraction_status IN ('succeeded', 'failed', 'insufficient')",
            name="information_contents_extraction_status_allowed",
        ),
        Index(
            "ix_information_contents_item_version",
            "information_item_id",
            "content_version",
            unique=True,
        ),
        Index("ix_information_contents_content_hash", "content_hash"),
    )

    information_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("information_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_origin: Mapped[str] = mapped_column(String(32), nullable=False)
    extracted_title: Mapped[str | None] = mapped_column(String(300))
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(80), nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ContentFetchAttempt(UuidPrimaryKeyMixin, Base):
    __tablename__ = "content_fetch_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="content_fetch_attempts_status_allowed",
        ),
        Index("ix_content_fetch_attempts_item_number", "information_item_id", "attempt_number", unique=True),
    )

    information_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("information_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(80))
    response_bytes: Mapped[int | None] = mapped_column(Integer)
    final_url: Mapped[str | None] = mapped_column(Text)
    attempt_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InformationAnalysisVersion(UuidPrimaryKeyMixin, Base):
    __tablename__ = "information_analysis_versions"
    __table_args__ = (
        CheckConstraint(
            "analysis_status IN ('succeeded', 'failed')",
            name="information_analysis_versions_status_allowed",
        ),
        Index(
            "ix_information_analysis_versions_item_version",
            "information_item_id",
            "version_number",
            unique=True,
        ),
        Index("ix_information_analysis_versions_task_id", "ai_task_id"),
    )

    information_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("information_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_tasks.id", ondelete="SET NULL"),
    )
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_provider_configs.id", ondelete="SET NULL"),
    )
    model_name: Mapped[str | None] = mapped_column(String(120))
    analysis_status: Mapped[str] = mapped_column(String(32), nullable=False)
    structured_result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    raw_response_redacted: Mapped[str | None] = mapped_column(Text)
    input_content_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InformationStockRelation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "information_stock_relations"
    __table_args__ = (
        CheckConstraint(
            "relation_origin IN ('ai', 'user', 'rule')",
            name="information_stock_relations_origin_allowed",
        ),
        CheckConstraint(
            "relation_status IN ('suggested', 'confirmed', 'rejected')",
            name="information_stock_relations_status_allowed",
        ),
        CheckConstraint(
            "relation_type IN ('directly_related', 'indirectly_related', 'mentioned', "
            "'compared', 'supply_chain', 'competitor', 'unknown')",
            name="information_stock_relations_type_allowed",
        ),
        Index("ix_information_stock_relations_item", "information_item_id"),
        Index("ix_information_stock_relations_stock", "stock_id"),
    )

    information_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("information_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    stock_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stocks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    relation_origin: Mapped[str] = mapped_column(String(32), nullable=False)
    relation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence_text: Mapped[str | None] = mapped_column(String(500))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InformationEntityMention(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "information_entity_mentions"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('company', 'industry', 'concept', 'product', 'person', "
            "'organization', 'commodity', 'policy', 'location', 'unknown')",
            name="information_entity_mentions_type_allowed",
        ),
        CheckConstraint(
            "origin IN ('ai', 'user', 'rule')",
            name="information_entity_mentions_origin_allowed",
        ),
        CheckConstraint(
            "status IN ('suggested', 'confirmed', 'rejected')",
            name="information_entity_mentions_status_allowed",
        ),
        Index("ix_information_entity_mentions_item", "information_item_id"),
    )

    information_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("information_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    relation: Mapped[str | None] = mapped_column(String(120))
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence_text: Mapped[str | None] = mapped_column(String(500))
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class VerificationItem(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "verification_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'verified', 'contradicted', 'unresolved', 'dismissed')",
            name="verification_items_status_allowed",
        ),
        Index("ix_verification_items_item_status", "information_item_id", "status"),
    )

    information_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("information_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("information_analysis_versions.id", ondelete="SET NULL"),
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    verification_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str | None] = mapped_column(String(32))
    evidence_needed: Mapped[str | None] = mapped_column(Text)
    user_note: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
