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


class CninfoAnnouncementProvider(AnnouncementProvider):
    source_code = "CNINFO"
    provider_adapter = "cninfo"
    endpoint = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    detail_url = "http://www.cninfo.com.cn/new/disclosure/detail"
    static_base_url = "http://static.cninfo.com.cn/"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def capabilities(self) -> list[str]:
        return ["announcement_list", "announcement_pdf"]

    async def health_check(self) -> ProviderResult:
        return ProviderResult(
            status=ProviderStatus.DISABLED if not self.settings.announcement_cninfo_enabled else ProviderStatus.PASS,
            provider_metadata={"experimental": True, "source_code": self.source_code},
        )

    async def list_announcements(self, query: AnnouncementQuery) -> ProviderResult:
        data = {
            "pageNum": 1,
            "pageSize": min(query.max_records, self.settings.announcement_max_records_per_run),
            "column": "szse",
            "tabName": "fulltext",
            "plate": "",
            "stock": "",
            "searchkey": "",
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": f"{query.date_from.isoformat()}~{query.date_to.isoformat()}",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        if query.symbols:
            data["stock"] = ",".join(symbol_without_exchange(symbol) for symbol in query.symbols[:5])
        headers = {
            "Referer": "http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        response = await provider_http_request(
            "POST",
            self.endpoint,
            data=data,
            headers=headers,
            timeout_seconds=self.settings.announcement_request_timeout_seconds,
            max_bytes=self.settings.announcement_max_response_bytes,
        )
        if not response.ok or not response.text:
            return ProviderResult(
                status=status_from_http_error(response.status_code, response.error_code),
                errors=[provider_error(response.error_code or str(response.status_code), "CNINFO list request failed")],
                metrics={"latency_ms": response.elapsed_ms, "response_bytes": response.response_bytes},
                request_count=1,
                failure_count=1,
            )
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            return ProviderResult(
                status=ProviderStatus.SOURCE_CHANGED,
                errors=[provider_error("JSON_PARSE_FAILED", "CNINFO response JSON shape changed")],
                metrics={"latency_ms": response.elapsed_ms, "response_bytes": response.response_bytes},
                request_count=1,
                failure_count=1,
            )
        rows = payload.get("announcements")
        if not isinstance(rows, list):
            return ProviderResult(
                status=ProviderStatus.SOURCE_CHANGED,
                errors=[provider_error("ANNOUNCEMENTS_FIELD_MISSING", "CNINFO announcements field missing")],
                metrics={"latency_ms": response.elapsed_ms, "response_bytes": response.response_bytes},
                request_count=1,
                failure_count=1,
            )
        fetched_at = datetime.now(UTC)
        records = [
            self.normalize(self._raw_from_row(row, fetched_at))
            for row in rows[: min(query.max_records, self.settings.announcement_max_records_per_run)]
            if isinstance(row, dict)
        ]
        return ProviderResult(
            status=ProviderStatus.PASS if records else ProviderStatus.DATA_INSUFFICIENT,
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
                    "experimental": True,
                    "authorization_status": "review_required",
                }
            ),
            request_count=1,
            success_count=1,
        )

    def _raw_from_row(self, row: dict[str, object], fetched_at: datetime) -> RawAnnouncementRecord:
        del fetched_at
        adjunct = row.get("adjunctUrl")
        document_url = f"{self.static_base_url}{adjunct}" if isinstance(adjunct, str) and adjunct else None
        sec_code = row.get("secCode")
        org_id = row.get("orgId")
        exchange = "SZ" if isinstance(org_id, str) and org_id.startswith("gssz") else "SH" if isinstance(org_id, str) and org_id.startswith("gssh") else None
        symbol = f"{sec_code}.{exchange}" if isinstance(sec_code, str) and exchange else str(sec_code) if sec_code else ""
        return RawAnnouncementRecord(
            provider_record_id=str(row.get("announcementId") or "") or None,
            title=str(row.get("announcementTitle") or ""),
            published_at=row.get("announcementTime"),
            source_page_url=self.detail_url,
            document_url=document_url,
            company_name=str(row.get("secName") or "") or None,
            stock_symbols=[symbol] if symbol else [],
            exchange=exchange,
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
