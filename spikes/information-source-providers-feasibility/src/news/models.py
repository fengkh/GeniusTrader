from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from ..hashing import stable_json_hash, text_hash
from ..normalization import normalize_title
from ..url_utils import normalize_url


@dataclass(slots=True)
class NewsRecord:
    provider: str
    provider_item_id: str | None
    title: str
    source_name: str
    author: str | None
    published_at: datetime | None
    updated_at: datetime | None
    source_url: str
    canonical_url: str | None
    summary: str | None
    extracted_text: str | None
    source_type: str
    related_symbols: list[str] = field(default_factory=list)
    related_company_names: list[str] = field(default_factory=list)
    related_entities: list[str] = field(default_factory=list)
    fetched_at: datetime | None = None
    extraction_status: str = "not_attempted"
    provider_payload_reference: dict[str, Any] = field(default_factory=dict)

    @property
    def normalized_title(self) -> str:
        return normalize_title(self.title)

    @property
    def content_length(self) -> int:
        return len(self.extracted_text or "")

    @property
    def content_hash(self) -> str | None:
        return text_hash(self.extracted_text) if self.extracted_text else None

    @property
    def deduplication_key(self) -> str:
        return stable_json_hash(
            {
                "title": self.normalized_title,
                "source": self.source_name,
                "published_at": self.published_at.isoformat() if self.published_at else None,
                "canonical": normalize_url(self.canonical_url or self.source_url),
            }
        )

    @property
    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        for field_name in ("title", "source_name", "published_at", "source_url"):
            value = getattr(self, field_name)
            if value is None or value == "":
                missing.append(field_name)
        if not self.extracted_text:
            missing.append("extracted_text")
        return missing

    @property
    def data_completeness(self) -> str:
        missing = set(self.missing_fields)
        if not missing:
            return "complete"
        if {"title", "source_name", "published_at", "source_url"} - missing:
            return "usable"
        if self.title and self.source_url:
            return "partial"
        return "insufficient"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["published_at"] = self.published_at.isoformat() if self.published_at else None
        value["updated_at"] = self.updated_at.isoformat() if self.updated_at else None
        value["fetched_at"] = self.fetched_at.isoformat() if self.fetched_at else None
        value["normalized_title"] = self.normalized_title
        value["content_length"] = self.content_length
        value["content_hash"] = self.content_hash
        value["deduplication_key"] = self.deduplication_key
        value["data_completeness"] = self.data_completeness
        value["missing_fields"] = self.missing_fields
        return value
