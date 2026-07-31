import json
from datetime import UTC, datetime
from typing import Any

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

LIST_FIELD_NAMES = ("announcements", "announcementList")
WRAPPER_FIELD_NAMES = ("data", "result")
TOTAL_FIELD_NAMES = ("totalRecordNum", "totalAnnouncement", "total", "totalCount")
BLOCKED_RESPONSE_TOKENS = ("captcha", "验证码", "访问过于频繁", "操作频繁", "forbidden", "access denied")


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
            error_code = "upstream_blocked" if _looks_blocked_response(response.text) else "upstream_invalid_response"
            return ProviderResult(
                status=ProviderStatus.ACCESS_DENIED if error_code == "upstream_blocked" else ProviderStatus.PARSE_ERROR,
                errors=[provider_error(error_code, "CNINFO response is not valid JSON")],
                metrics={"latency_ms": response.elapsed_ms, "response_bytes": response.response_bytes},
                request_count=1,
                failure_count=1,
            )

        rows_result = _extract_announcement_rows(payload)
        if rows_result.error_code:
            return ProviderResult(
                status=ProviderStatus.SOURCE_CHANGED,
                errors=[provider_error(rows_result.error_code, rows_result.error_summary)],
                metrics={
                    "latency_ms": response.elapsed_ms,
                    "response_bytes": response.response_bytes,
                    "top_level_fields": _field_names(payload),
                    "announcement_list_path": rows_result.path,
                },
                request_count=1,
                failure_count=1,
            )
        rows = rows_result.rows
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
                "announcement_list_path": rows_result.path,
                "total_record_count": rows_result.total_count,
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
        adjunct = _first_present(row, "adjunctUrl", "pdfUrl", "pdf_url", "documentUrl")
        document_url = f"{self.static_base_url}{adjunct}" if isinstance(adjunct, str) and adjunct else None
        sec_code = _first_present(row, "secCode", "stockCode", "stock_code")
        org_id = _first_present(row, "orgId", "orgID")
        exchange = "SZ" if isinstance(org_id, str) and org_id.startswith("gssz") else "SH" if isinstance(org_id, str) and org_id.startswith("gssh") else None
        symbol = f"{sec_code}.{exchange}" if isinstance(sec_code, str) and exchange else str(sec_code) if sec_code else ""
        source_page_url = _first_present(row, "sourceUrl", "source_url", "detailUrl") or self.detail_url
        raw_payload = {
            key: value
            for key, value in {
                "announcementId": _first_present(row, "announcementId", "announcement_id", "id"),
                "announcementTitle": _first_present(row, "announcementTitle", "title"),
                "announcementTime": _first_present(row, "announcementTime", "announcementDate", "announcement_date", "publishTime"),
                "secCode": sec_code,
                "secName": _first_present(row, "secName", "stockName", "stock_name"),
                "orgId": org_id,
                "source_url": source_page_url,
                "pdf_url": document_url,
                "content_availability": "metadata_only",
                "provider_code": self.source_code,
            }.items()
            if value not in (None, "")
        }
        return RawAnnouncementRecord(
            provider_record_id=str(_first_present(row, "announcementId", "announcement_id", "id") or "") or None,
            title=str(_first_present(row, "announcementTitle", "title") or ""),
            published_at=_first_present(row, "announcementTime", "announcementDate", "announcement_date", "publishTime"),
            source_page_url=str(source_page_url),
            document_url=document_url,
            company_name=str(_first_present(row, "secName", "stockName", "stock_name") or "") or None,
            stock_symbols=[symbol] if symbol else [],
            exchange=exchange,
            raw_payload=raw_payload,
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


class _RowsResult:
    def __init__(
        self,
        *,
        rows: list[dict[str, object]],
        path: str | None,
        total_count: int | None,
        error_code: str | None = None,
        error_summary: str = "",
    ) -> None:
        self.rows = rows
        self.path = path
        self.total_count = total_count
        self.error_code = error_code
        self.error_summary = error_summary


def _extract_announcement_rows(payload: Any) -> _RowsResult:
    if not isinstance(payload, dict):
        return _RowsResult(
            rows=[],
            path=None,
            total_count=None,
            error_code="ANNOUNCEMENTS_FIELD_MISSING",
            error_summary="CNINFO top-level response is not an object",
        )
    for field_name in LIST_FIELD_NAMES:
        if field_name in payload:
            return _rows_from_value(payload[field_name], path=field_name, total_count=_total_count(payload))
    for wrapper_name in WRAPPER_FIELD_NAMES:
        wrapper = payload.get(wrapper_name)
        if isinstance(wrapper, dict):
            for field_name in LIST_FIELD_NAMES:
                if field_name in wrapper:
                    return _rows_from_value(wrapper[field_name], path=f"{wrapper_name}.{field_name}", total_count=_total_count(wrapper, fallback=payload))
    return _RowsResult(
        rows=[],
        path=None,
        total_count=_total_count(payload),
        error_code="ANNOUNCEMENTS_FIELD_MISSING",
        error_summary="CNINFO announcements field missing",
    )


def _rows_from_value(value: Any, *, path: str, total_count: int | None) -> _RowsResult:
    if isinstance(value, list):
        return _RowsResult(rows=[row for row in value if isinstance(row, dict)], path=path, total_count=total_count)
    if value is None and total_count == 0:
        return _RowsResult(rows=[], path=path, total_count=total_count)
    return _RowsResult(
        rows=[],
        path=path,
        total_count=total_count,
        error_code="ANNOUNCEMENTS_FIELD_MISSING",
        error_summary="CNINFO announcements field is not a list",
    )


def _total_count(payload: dict[str, Any], *, fallback: dict[str, Any] | None = None) -> int | None:
    for source in (payload, fallback):
        if not isinstance(source, dict):
            continue
        for field_name in TOTAL_FIELD_NAMES:
            value = source.get(field_name)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
    return None


def _looks_blocked_response(text: str) -> bool:
    lowered = text[:1000].lower()
    return any(token in lowered for token in BLOCKED_RESPONSE_TOKENS)


def _field_names(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    return sorted(str(key) for key in payload.keys())


def _first_present(row: dict[str, object], *keys: str) -> object | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None
