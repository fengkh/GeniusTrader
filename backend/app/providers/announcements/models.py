from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.providers.statuses import ProviderStatus


@dataclass(frozen=True, slots=True)
class RawAnnouncementRecord:
    provider_record_id: str | None
    title: str
    published_at: str | int | float | None
    source_page_url: str
    document_url: str | None
    company_name: str | None
    stock_symbols: list[str]
    exchange: str | None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NormalizedAnnouncement:
    source_code: str
    provider_announcement_id: str | None
    title: str
    normalized_title: str
    announcement_type: str
    announcement_type_confidence: float
    announcement_type_basis: dict[str, Any]
    published_at: datetime | None
    company_name: str | None
    stock_symbols: list[str]
    exchange: str | None
    source_page_url: str
    document_url: str | None
    attachment_urls: list[str]
    is_pdf: bool
    is_correction: bool
    corrected_announcement_id: str | None
    raw_metadata_hash: str
    deduplication_key: str
    data_completeness: str
    missing_fields: list[str]
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class ProviderResult:
    status: ProviderStatus
    records: list[NormalizedAnnouncement] = field(default_factory=list)
    next_cursor: str | None = None
    errors: list[dict[str, str]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0


class FutureModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GovernmentDocumentDraft(FutureModel):
    external_source_id: str | None = None
    provider_document_id: str | None = None
    title: str
    normalized_title: str | None = None
    document_number: str | None = None
    issuing_authorities: list[str] = []
    authority_level: str | None = None
    jurisdiction: str | None = None
    document_type: str = "unknown"
    published_at: datetime | None = None
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    policy_status: str | None = None
    policy_topics: list[str] = []
    affected_regions: list[str] = []
    affected_industries: list[str] = []
    mentioned_companies: list[str] = []
    related_symbols: list[str] = []
    source_url: str | None = None
    attachment_urls: list[str] = []
    interpretation_url: str | None = None
    is_policy_interpretation: bool = False
    supersedes_document_id: str | None = None
    data_completeness: str = "unknown"
    missing_fields: list[str] = []


class InternationalOfficialDocumentDraft(FutureModel):
    external_source_id: str | None = None
    provider_document_id: str | None = None
    title: str
    issuing_organization: str | None = None
    jurisdiction: str | None = None
    country_code: str | None = None
    document_type: str = "unknown"
    published_at: datetime | None = None
    effective_at: datetime | None = None
    source_url: str | None = None
    attachment_urls: list[str] = []
    topics: list[str] = []
    affected_countries: list[str] = []
    affected_industries: list[str] = []
    mentioned_companies: list[str] = []
    related_symbols: list[str] = []
    sanctions_or_controls: list[str] = []
    language: str | None = None
    translated_summary: str | None = None
    translation_status: str = "not_translated"
    data_completeness: str = "unknown"


class LicensedMediaItemDraft(FutureModel):
    external_source_id: str | None = None
    provider_item_id: str | None = None
    title: str
    published_at: datetime | None = None
    updated_at: datetime | None = None
    author: str | None = None
    source_url: str | None = None
    language: str | None = None
    licensed_summary: str | None = None
    licensed_excerpt: str | None = None
    full_text_available: bool = False
    full_text_storage_allowed: bool = False
    ai_processing_allowed: bool = False
    redistribution_allowed: bool = False
    related_symbols: list[str] = []
    related_entities: list[str] = []
    content_hash: str | None = None
    license_reference: str | None = None

