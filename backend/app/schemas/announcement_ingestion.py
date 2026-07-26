import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EXPERIMENTAL_NOTICE = "当前公告同步功能处于实验阶段，数据来源、完整性、及时性、稳定性及使用授权尚未最终确认。"
DETAIL_NOTICE = "公告内容来自公开来源。当前功能处于实验阶段，系统不保证数据完整性、及时性或长期可用性。原文、版权及使用权限以来源网站及相关授权为准。"


class AnnouncementSyncRunCreate(BaseModel):
    source_code: str = Field(max_length=80)
    date_from: date
    date_to: date
    stock_ids: list[uuid.UUID] = Field(default_factory=list)
    use_current_watchlist: bool = True


class ProviderSyncRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_source_id: uuid.UUID
    capability: str
    triggered_by_user_id: uuid.UUID
    status: str
    date_from: date
    date_to: date
    requested_symbols: list[str]
    request_count: int
    success_count: int
    failure_count: int
    record_count: int
    candidate_count: int
    created_record_count: int
    updated_record_count: int
    duplicate_record_count: int
    error_code: str | None
    error_summary: str | None
    metrics: dict
    provider_metadata: dict
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    experimental_notice: str = EXPERIMENTAL_NOTICE


class AnnouncementCandidateSummaryOut(BaseModel):
    id: uuid.UUID
    announcement_record_id: uuid.UUID
    sync_run_id: uuid.UUID | None
    status: str
    match_type: str
    matched_stock_id: uuid.UUID | None
    matched_watchlist_item_id: uuid.UUID | None
    title: str
    announcement_type: str
    announcement_type_confidence: float
    published_at: datetime | None
    company_name: str | None
    stock_symbols: list[str]
    source_code: str
    source_display_name: str
    source_tier: str
    authorization_status: str
    data_completeness: str
    missing_fields: list[str]
    is_pdf: bool
    document_url: str | None
    document_extract_status: str
    document_page_count: int | None
    document_character_count: int | None
    created_at: datetime
    updated_at: datetime
    experimental_notice: str = EXPERIMENTAL_NOTICE


class AnnouncementCandidateDetailOut(AnnouncementCandidateSummaryOut):
    normalized_title: str
    announcement_type_basis: dict
    exchange: str | None
    source_page_url: str
    attachment_urls: list[str]
    is_correction: bool
    corrected_announcement_id: str | None
    raw_metadata_hash: str
    deduplication_key: str
    fetched_at: datetime
    first_seen_at: datetime
    last_seen_at: datetime
    source_authority_level: str
    source_access_mode: str
    redistribution_status: str
    commercial_use_status: str
    legal_review_status: str
    source_limitations: list[str]
    match_evidence: dict
    document_extracted_at: datetime | None
    document_limitations: list[str]
    reviewed_at: datetime | None
    dismissed_at: datetime | None
    imported_at: datetime | None
    information_item_id: uuid.UUID | None = None
    detail_notice: str = DETAIL_NOTICE


class AnnouncementCandidatePatch(BaseModel):
    status: Literal["pending", "reviewed", "dismissed"]


class AnnouncementDocumentExtractOut(BaseModel):
    candidate_id: uuid.UUID
    document_extract_status: str
    document_extracted_at: datetime | None
    page_count: int | None
    character_count: int | None
    limitations: list[str]
    experimental_notice: str = EXPERIMENTAL_NOTICE


class AnnouncementImportRequest(BaseModel):
    import_mode: Literal["metadata_only", "extracted_document", "user_supplemented"]
    title_override: str | None = Field(default=None, max_length=300)
    user_note: str | None = None
    supplemented_text: str | None = None


class AnnouncementImportOut(BaseModel):
    candidate_id: uuid.UUID
    information_item_id: uuid.UUID
    import_mode: str
    already_imported: bool = False
    created_at: datetime
