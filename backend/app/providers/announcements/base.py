from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.providers.announcements.models import (
    NormalizedAnnouncement,
    ProviderResult,
    RawAnnouncementRecord,
)


@dataclass(frozen=True, slots=True)
class AnnouncementQuery:
    date_from: date
    date_to: date
    symbols: list[str]
    cursor: str | None
    max_records: int


class AnnouncementProvider(ABC):
    source_code: str
    provider_adapter: str

    @abstractmethod
    def capabilities(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> ProviderResult:
        raise NotImplementedError

    @abstractmethod
    async def list_announcements(self, query: AnnouncementQuery) -> ProviderResult:
        raise NotImplementedError

    @abstractmethod
    async def fetch_announcement(self, provider_record_id: str) -> RawAnnouncementRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def fetch_document(self, document_url: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, raw_record: RawAnnouncementRecord) -> NormalizedAnnouncement:
        raise NotImplementedError

    @abstractmethod
    def build_next_cursor(self, result: ProviderResult) -> str | None:
        raise NotImplementedError


def provider_error(code: str, summary: str) -> dict[str, str]:
    return {"code": code[:80], "summary": summary[:300]}


def compact_provider_metadata(value: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, item in value.items():
        lowered = key.lower()
        if lowered in {"cookie", "set-cookie", "authorization", "token", "api_key", "password"}:
            safe[key] = "[redacted]"
        elif isinstance(item, str) and len(item) > 500:
            safe[key] = f"{item[:500]}..."
        else:
            safe[key] = item
    return safe
