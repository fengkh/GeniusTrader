import json
from datetime import UTC, datetime

from app.core.config import Settings
from app.providers.announcements.base import (
    AnnouncementProvider,
    AnnouncementQuery,
    compact_provider_metadata,
    provider_error,
)
from app.providers.announcements.models import (
    NormalizedAnnouncement,
    ProviderResult,
    RawAnnouncementRecord,
)
from app.providers.announcements.normalization import (
    build_normalized_announcement,
    symbol_without_exchange,
)
from app.providers.base import provider_http_request
from app.providers.statuses import ProviderStatus, status_from_http_error


class SseAnnouncementProvider(AnnouncementProvider):
    source_code = "SSE_DISCLOSURE"
    provider_adapter = "sse"
    endpoint = "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do"
    source_page_url = "https://www.sse.com.cn/disclosure/listedinfo/announcement/"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def capabilities(self) -> list[str]:
        return ["announcement_list", "announcement_pdf"]

    async def health_check(self) -> ProviderResult:
        return ProviderResult(
            status=ProviderStatus.DISABLED if not self.settings.announcement_sse_enabled else ProviderStatus.PARTIAL,
            provider_metadata={"experimental_limited": True, "source_code": self.source_code},
        )

    async def list_announcements(self, query: AnnouncementQuery) -> ProviderResult:
        params = {
            "jsonCallBack": "",
            "isPagination": "true",
            "pageHelp.pageSize": str(min(query.max_records, self.settings.announcement_max_records_per_run)),
            "pageHelp.pageNo": "1",
            "pageHelp.beginPage": "1",
            "pageHelp.cacheSize": "1",
            "pageHelp.endPage": "1",
            "productId": symbol_without_exchange(query.symbols[0]) if query.symbols else "",
            "securityType": "0101,120100,020100,020200,120200",
            "reportType": "ALL",
            "beginDate": query.date_from.isoformat(),
            "endDate": query.date_to.isoformat(),
        }
        response = await provider_http_request(
            "GET",
            self.endpoint,
            params=params,
            headers={"Referer": self.source_page_url},
            timeout_seconds=self.settings.announcement_request_timeout_seconds,
            max_bytes=self.settings.announcement_max_response_bytes,
        )
        if not response.ok or not response.text:
            return ProviderResult(
                status=status_from_http_error(response.status_code, response.error_code),
                errors=[provider_error(response.error_code or str(response.status_code), "SSE list request failed")],
                metrics={"latency_ms": response.elapsed_ms, "response_bytes": response.response_bytes},
                request_count=1,
                failure_count=1,
            )
        try:
            payload = json.loads(response.text.strip().strip("();"))
        except json.JSONDecodeError:
            return ProviderResult(
                status=ProviderStatus.SOURCE_CHANGED,
                errors=[provider_error("JSON_PARSE_FAILED", "SSE response JSON shape changed")],
                metrics={"latency_ms": response.elapsed_ms, "response_bytes": response.response_bytes},
                request_count=1,
                failure_count=1,
            )
        rows = payload.get("result")
        if not isinstance(rows, list):
            return ProviderResult(
                status=ProviderStatus.DATA_INSUFFICIENT,
                errors=[provider_error("RESULT_FIELD_MISSING", "SSE result field missing or empty")],
                metrics={"latency_ms": response.elapsed_ms, "response_bytes": response.response_bytes},
                request_count=1,
                success_count=1,
            )
        records = [
            self.normalize(self._raw_from_row(row))
            for row in rows[: min(query.max_records, self.settings.announcement_max_records_per_run)]
            if isinstance(row, dict)
        ]
        return ProviderResult(
            status=ProviderStatus.PARTIAL if records else ProviderStatus.DATA_INSUFFICIENT,
            records=records,
            next_cursor=self.build_next_cursor_from_records(records),
            metrics={
                "latency_ms": response.elapsed_ms,
                "response_bytes": response.response_bytes,
                "supports_date_range": True,
                "supports_symbol_filter": True,
            },
            provider_metadata=compact_provider_metadata(
                {
                    "endpoint": self.endpoint,
                    "experimental_limited": True,
                    "authorization_status": "review_required",
                }
            ),
            request_count=1,
            success_count=1,
        )

    def _raw_from_row(self, row: dict[str, object]) -> RawAnnouncementRecord:
        document_url = row.get("URL")
        if isinstance(document_url, str) and document_url.startswith("/"):
            document_url = f"https://www.sse.com.cn{document_url}"
        code = row.get("SECURITY_CODE") or row.get("PRODUCTID")
        symbol = f"{code}.SH" if code else ""
        return RawAnnouncementRecord(
            provider_record_id=str(row.get("BULLETINID") or row.get("ROWNUM") or "") or None,
            title=str(row.get("TITLE") or row.get("BULLETIN_HEADING") or ""),
            published_at=row.get("SSEDATE") or row.get("BULLETIN_DATE"),
            source_page_url=self.source_page_url,
            document_url=document_url if isinstance(document_url, str) else None,
            company_name=str(row.get("SECURITY_NAME") or row.get("COMPANY_ABBR") or "") or None,
            stock_symbols=[symbol] if symbol else [],
            exchange="SH",
            raw_payload=row,
        )

    async def fetch_announcement(self, provider_record_id: str) -> RawAnnouncementRecord | None:
        del provider_record_id
        return None

    async def fetch_document(self, document_url: str) -> bytes:
        response = await provider_http_request(
            "GET",
            document_url,
            timeout_seconds=self.settings.announcement_request_timeout_seconds,
            max_bytes=self.settings.announcement_max_pdf_bytes,
        )
        return response.content if response.ok else b""

    def normalize(self, raw_record: RawAnnouncementRecord) -> NormalizedAnnouncement:
        return build_normalized_announcement(
            source_code=self.source_code,
            raw=raw_record,
            fetched_at=datetime.now(UTC),
        )

    def build_next_cursor(self, result: ProviderResult) -> str | None:
        return self.build_next_cursor_from_records(result.records)

    @staticmethod
    def build_next_cursor_from_records(records: list[NormalizedAnnouncement]) -> str | None:
        ordered = sorted(
            [record for record in records if record.published_at],
            key=lambda item: (item.published_at or datetime.min.replace(tzinfo=UTC), item.provider_announcement_id or ""),
        )
        if not ordered:
            return None
        last = ordered[-1]
        return f"{last.published_at.isoformat()}|{last.provider_announcement_id or ''}"
