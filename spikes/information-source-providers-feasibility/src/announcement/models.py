from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from ..date_utils import effective_date
from ..hashing import stable_json_hash
from ..normalization import normalize_title
from ..url_utils import normalize_url


REQUIRED_FIELDS = ["provider", "provider_announcement_id", "title", "published_at", "source_page_url"]


@dataclass(slots=True)
class AnnouncementRecord:
    provider: str
    provider_announcement_id: str | None
    announcement_id_stability: str
    title: str
    announcement_type: str
    published_at: datetime | None
    company_name: str | None
    stock_symbols: list[str]
    exchange: str | None
    source_page_url: str
    document_url: str | None = None
    attachment_urls: list[str] = field(default_factory=list)
    document_content_type: str | None = None
    document_size_bytes: int | None = None
    is_pdf: bool = False
    is_correction: bool = False
    corrected_announcement_id: str | None = None
    fetched_at: datetime | None = None
    raw_metadata_hash: str | None = None
    provider_payload_reference: dict[str, Any] = field(default_factory=dict)

    @property
    def effective_date(self) -> str | None:
        return effective_date(self.published_at)

    @property
    def normalized_title(self) -> str:
        return normalize_title(self.title)

    @property
    def deduplication_key(self) -> str:
        payload = {
            "provider_id": self.provider_announcement_id,
            "title": self.normalized_title,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "symbols": sorted(self.stock_symbols),
            "document_url": normalize_url(self.document_url) if self.document_url else None,
        }
        return stable_json_hash(payload)

    @property
    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        for field_name in REQUIRED_FIELDS:
            value = getattr(self, field_name)
            if value is None or value == "":
                missing.append(field_name)
        if not self.stock_symbols:
            missing.append("stock_symbols")
        if not self.document_url:
            missing.append("document_url")
        return missing

    @property
    def data_completeness(self) -> str:
        missing = set(self.missing_fields)
        if not missing:
            return "complete"
        if not self.title or not self.source_page_url:
            return "insufficient"
        core_missing = {"provider_announcement_id", "published_at"} & missing
        if not core_missing:
            return "usable"
        if self.title and self.source_page_url:
            return "partial"
        return "insufficient"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["published_at"] = self.published_at.isoformat() if self.published_at else None
        value["effective_date"] = self.effective_date
        value["fetched_at"] = self.fetched_at.isoformat() if self.fetched_at else None
        value["raw_metadata_hash"] = self.raw_metadata_hash or stable_json_hash(self.provider_payload_reference)
        value["normalized_title"] = self.normalized_title
        value["deduplication_key"] = self.deduplication_key
        value["data_completeness"] = self.data_completeness
        value["missing_fields"] = self.missing_fields
        return value
