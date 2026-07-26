import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.information import InformationItem
from app.models.stock import Stock
from app.models.user import User
from app.models.watchlist import UserWatchlistItem

SOURCE_CATEGORY_VALUES = (
    "'exchange_announcement', 'company_disclosure', 'government_policy', "
    "'government_notice', 'regulator_release', 'regulator_enforcement', "
    "'central_bank_release', 'statistics_release', 'international_official', "
    "'multilateral_organization', 'licensed_financial_media', 'public_financial_media', "
    "'company_news', 'rss', 'public_web', 'user_submitted', 'social_media', 'unknown'"
)

AUTHORITY_LEVEL_VALUES = (
    "'exchange', 'company', 'central_government', 'ministry', 'national_regulator', "
    "'provincial_government', 'provincial_department', 'municipal_government', "
    "'municipal_department', 'international_regulator', 'central_bank', "
    "'multilateral_organization', 'licensed_media', 'public_media', 'user', "
    "'social', 'unknown'"
)

PROVIDER_HEALTH_VALUES = (
    "'unknown', 'pass', 'partial', 'data_insufficient', 'not_available', "
    "'network_error', 'timeout', 'rate_limited', 'access_denied', 'source_changed', "
    "'parse_error', 'content_unavailable', 'legal_hold', 'disabled'"
)


class ExternalSource(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_sources"
    __table_args__ = (
        CheckConstraint(f"source_category IN ({SOURCE_CATEGORY_VALUES})", name="external_sources_category_allowed"),
        CheckConstraint(f"authority_level IN ({AUTHORITY_LEVEL_VALUES})", name="external_sources_authority_allowed"),
        CheckConstraint("source_tier IN ('s', 'a', 'b', 'c', 'd', 'unknown')", name="external_sources_tier_allowed"),
        CheckConstraint(
            "access_mode IN ('official_api', 'public_endpoint', 'rss', 'public_html', "
            "'licensed_api', 'manual_url', 'manual_text', 'unavailable')",
            name="external_sources_access_mode_allowed",
        ),
        CheckConstraint(
            "authorization_status IN ('testing_only', 'unclear', 'review_required', 'approved', 'prohibited')",
            name="external_sources_authorization_allowed",
        ),
        CheckConstraint(
            "redistribution_status IN ('unclear', 'metadata_only', 'excerpt_allowed', "
            "'full_text_allowed', 'prohibited')",
            name="external_sources_redistribution_allowed",
        ),
        CheckConstraint(
            "commercial_use_status IN ('unclear', 'review_required', 'approved', 'prohibited')",
            name="external_sources_commercial_use_allowed",
        ),
        CheckConstraint(
            "legal_review_status IN ('not_started', 'pending', 'reviewed', 'blocked')",
            name="external_sources_legal_review_allowed",
        ),
        CheckConstraint(f"health_status IN ({PROVIDER_HEALTH_VALUES})", name="external_sources_health_allowed"),
        Index("uq_external_sources_source_code", "source_code", unique=True),
        Index("ix_external_sources_category", "source_category"),
        Index("ix_external_sources_enabled", "enabled", "experimental"),
    )

    source_code: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    publisher_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_category: Mapped[str] = mapped_column(String(64), nullable=False)
    authority_level: Mapped[str] = mapped_column(String(64), nullable=False)
    source_tier: Mapped[str] = mapped_column(String(16), nullable=False)
    jurisdiction: Mapped[str | None] = mapped_column(String(120))
    country_code: Mapped[str | None] = mapped_column(String(8))
    region_code: Mapped[str | None] = mapped_column(String(32))
    city_code: Mapped[str | None] = mapped_column(String(32))
    official_domain: Mapped[str | None] = mapped_column(String(200))
    access_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    content_language: Mapped[str] = mapped_column(String(16), nullable=False, default="zh-CN")
    provider_adapter: Mapped[str | None] = mapped_column(String(80))
    authorization_status: Mapped[str] = mapped_column(String(40), nullable=False)
    redistribution_status: Mapped[str] = mapped_column(String(40), nullable=False)
    commercial_use_status: Mapped[str] = mapped_column(String(40), nullable=False)
    legal_review_status: Mapped[str] = mapped_column(String(40), nullable=False)
    health_status: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    experimental: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    limitations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class ProviderSyncRun(UuidPrimaryKeyMixin, Base):
    __tablename__ = "provider_sync_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'complete', 'partial', 'failed', 'data_insufficient', "
            "'not_available', 'network_error', 'timeout', 'rate_limited', 'access_denied', "
            "'source_changed', 'parse_error', 'content_unavailable', 'legal_hold', 'disabled')",
            name="provider_sync_runs_status_allowed",
        ),
        Index("ix_provider_sync_runs_user_started", "triggered_by_user_id", "started_at"),
        Index("ix_provider_sync_runs_source_capability", "external_source_id", "capability"),
    )

    external_source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("external_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    capability: Mapped[str] = mapped_column(String(80), nullable=False)
    triggered_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    requested_symbols: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_summary: Mapped[str | None] = mapped_column(String(500))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    external_source: Mapped[ExternalSource] = relationship()
    triggered_by_user: Mapped[User] = relationship()


class ProviderSyncState(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_sync_states"
    __table_args__ = (
        CheckConstraint(f"health_status IN ({PROVIDER_HEALTH_VALUES})", name="provider_sync_states_health_allowed"),
        Index(
            "uq_provider_sync_states_scope",
            "external_source_id",
            "capability",
            "user_id",
            "scope_type",
            "scope_key",
            unique=True,
        ),
    )

    external_source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("external_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    capability: Mapped[str] = mapped_column(String(80), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(160), nullable=False)
    cursor_type: Mapped[str | None] = mapped_column(String(80))
    cursor_value: Mapped[str | None] = mapped_column(Text)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_item_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_provider_item_id: Mapped[str | None] = mapped_column(String(120))
    overlap_window_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=86400)
    health_status: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    last_error_code: Mapped[str | None] = mapped_column(String(80))

    external_source: Mapped[ExternalSource] = relationship()
    user: Mapped[User] = relationship()


class AnnouncementRecord(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "announcement_records"
    __table_args__ = (
        CheckConstraint(
            "data_completeness IN ('complete', 'usable', 'partial', 'insufficient')",
            name="announcement_records_completeness_allowed",
        ),
        Index("uq_announcement_records_provider_id", "external_source_id", "provider_announcement_id", unique=True),
        Index("ix_announcement_records_deduplication_key", "deduplication_key"),
        Index("ix_announcement_records_source_published", "external_source_id", "published_at"),
        Index("ix_announcement_records_type", "announcement_type"),
    )

    external_source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("external_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_code: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_announcement_id: Mapped[str | None] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False)
    announcement_type: Mapped[str] = mapped_column(String(80), nullable=False)
    announcement_type_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    announcement_type_basis: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    company_name: Mapped[str | None] = mapped_column(String(200))
    stock_symbols: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    exchange: Mapped[str | None] = mapped_column(String(16))
    source_page_url: Mapped[str] = mapped_column(Text, nullable=False)
    document_url: Mapped[str | None] = mapped_column(Text)
    attachment_urls: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_pdf: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_correction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    corrected_announcement_id: Mapped[str | None] = mapped_column(String(160))
    raw_metadata_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(64), nullable=False)
    data_completeness: Mapped[str] = mapped_column(String(32), nullable=False)
    missing_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    external_source: Mapped[ExternalSource] = relationship()


class UserAnnouncementCandidate(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_announcement_candidates"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'reviewed', 'dismissed', 'imported', 'unavailable')",
            name="user_announcement_candidates_status_allowed",
        ),
        CheckConstraint(
            "match_type IN ('exact_symbol', 'provider_metadata', 'exact_company_name', "
            "'ambiguous_name', 'unmatched')",
            name="user_announcement_candidates_match_type_allowed",
        ),
        CheckConstraint(
            "document_extract_status IN ('not_requested', 'succeeded', 'failed', 'unavailable', "
            "'too_large', 'too_many_pages', 'text_unavailable')",
            name="user_announcement_candidates_document_extract_status_allowed",
        ),
        Index("uq_user_announcement_candidates_user_record", "user_id", "announcement_record_id", unique=True),
        Index("ix_user_announcement_candidates_user_status", "user_id", "status", "created_at"),
        Index("ix_user_announcement_candidates_stock", "matched_stock_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    announcement_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("announcement_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    sync_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("provider_sync_runs.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    match_type: Mapped[str] = mapped_column(String(40), nullable=False)
    matched_stock_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stocks.id", ondelete="SET NULL"),
    )
    matched_watchlist_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_watchlist_items.id", ondelete="SET NULL"),
    )
    match_evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    document_extract_status: Mapped[str] = mapped_column(String(40), nullable=False, default="not_requested")
    document_extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    document_page_count: Mapped[int | None] = mapped_column(Integer)
    document_character_count: Mapped[int | None] = mapped_column(Integer)
    document_limitations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()
    announcement_record: Mapped[AnnouncementRecord] = relationship()
    sync_run: Mapped[ProviderSyncRun | None] = relationship()
    matched_stock: Mapped[Stock | None] = relationship()
    matched_watchlist_item: Mapped[UserWatchlistItem | None] = relationship()


class InformationIngestionLink(UuidPrimaryKeyMixin, Base):
    __tablename__ = "information_ingestion_links"
    __table_args__ = (
        CheckConstraint("source_record_type IN ('announcement')", name="information_ingestion_links_record_type_allowed"),
        CheckConstraint(
            "import_mode IN ('metadata_only', 'extracted_document', 'user_supplemented')",
            name="information_ingestion_links_import_mode_allowed",
        ),
        Index("uq_information_ingestion_links_user_candidate", "user_id", "candidate_id", unique=True),
        Index("ix_information_ingestion_links_information", "information_item_id"),
        Index("ix_information_ingestion_links_record", "announcement_record_id"),
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
    external_source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("external_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_record_type: Mapped[str] = mapped_column(String(40), nullable=False)
    announcement_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("announcement_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_announcement_candidates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    import_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship()
    information_item: Mapped[InformationItem] = relationship()
    external_source: Mapped[ExternalSource] = relationship()
    announcement_record: Mapped[AnnouncementRecord] = relationship()
    candidate: Mapped[UserAnnouncementCandidate] = relationship()
