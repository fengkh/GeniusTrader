from datetime import UTC, datetime

from app.core.config import Settings
from app.providers.announcements.base import AnnouncementProvider, AnnouncementQuery, provider_error
from app.providers.announcements.models import (
    NormalizedAnnouncement,
    ProviderResult,
    RawAnnouncementRecord,
)
from app.providers.announcements.normalization import (
    build_normalized_announcement,
    normalize_symbol,
)
from app.providers.statuses import ProviderStatus


class BseAnnouncementProvider(AnnouncementProvider):
    source_code = "BSE_DISCLOSURE"
    provider_adapter = "bse"
    source_page_url = "https://www.bse.cn/disclosure/announcement.html"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def capabilities(self) -> list[str]:
        return ["announcement_list", "announcement_pdf"]

    async def health_check(self) -> ProviderResult:
        if not self.settings.announcement_bse_enabled:
            return ProviderResult(
                status=ProviderStatus.DISABLED,
                provider_metadata={"source_code": self.source_code, "official": True},
            )
        return ProviderResult(
            status=ProviderStatus.DATA_INSUFFICIENT,
            errors=[provider_error("BSE_SMOKE_PENDING", "BSE real provider smoke is pending")],
            provider_metadata={"source_code": self.source_code, "official": True},
        )

    async def list_announcements(self, query: AnnouncementQuery) -> ProviderResult:
        del query
        return ProviderResult(
            status=ProviderStatus.DATA_INSUFFICIENT,
            errors=[provider_error("BSE_SMOKE_PENDING", "BSE official endpoint smoke is pending")],
            metrics={"network": False, "official_source": True},
            provider_metadata={
                "source_page_url": self.source_page_url,
                "authorization_status": "review_required",
            },
            request_count=0,
            success_count=0,
        )

    async def fetch_announcement(self, provider_record_id: str) -> RawAnnouncementRecord | None:
        del provider_record_id
        return None

    async def fetch_document(self, document_url: str) -> bytes:
        del document_url
        return b""

    def normalize(self, raw_record: RawAnnouncementRecord) -> NormalizedAnnouncement:
        symbols = []
        for symbol in raw_record.stock_symbols:
            try:
                normalized = normalize_symbol(symbol)
            except ValueError:
                continue
            if normalized.endswith(".BJ"):
                symbols.append(normalized)
        current_bj_symbols = [symbol for symbol in dict.fromkeys(symbols) if symbol[:6].isdigit()]
        raw = RawAnnouncementRecord(
            provider_record_id=raw_record.provider_record_id,
            title=raw_record.title,
            published_at=raw_record.published_at,
            source_page_url=raw_record.source_page_url or self.source_page_url,
            document_url=raw_record.document_url,
            company_name=raw_record.company_name,
            stock_symbols=current_bj_symbols,
            exchange="BJ",
            raw_payload=raw_record.raw_payload,
        )
        return build_normalized_announcement(
            source_code=self.source_code,
            raw=raw,
            fetched_at=datetime.now(UTC),
        )

    def build_next_cursor(self, result: ProviderResult) -> str | None:
        ordered = sorted(
            [record for record in result.records if record.published_at],
            key=lambda item: (item.published_at or datetime.min.replace(tzinfo=UTC), item.provider_announcement_id or ""),
        )
        if not ordered:
            return None
        last = ordered[-1]
        return f"{last.published_at.isoformat()}|{last.provider_announcement_id or ''}"
