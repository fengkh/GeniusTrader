import json
from typing import Any

from app.core.config import Settings
from app.providers.base import provider_http_request
from app.providers.securities.base import SecurityMasterProvider
from app.providers.securities.models import (
    SecurityMasterCapability,
    SecurityMasterQuery,
    SecurityMasterRecord,
    SecurityMasterResult,
)
from app.providers.securities.normalization import (
    completeness_for,
    fetched_at_now,
    first_non_empty,
    metadata_hash,
    normalize_board,
    normalize_code,
    normalize_listing_status,
    normalize_security_type,
    normalize_symbol,
    parse_date,
    pinyin_fields,
)
from app.providers.statuses import ProviderStatus, status_from_http_error


class SseSecurityMasterProvider(SecurityMasterProvider):
    source_code = "SSE_SECURITY_MASTER"
    endpoint = "https://query.sse.com.cn/security/stock/getStockListData2.do"
    stock_types = ("1", "8")

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def capabilities(self) -> list[SecurityMasterCapability]:
        return [
            SecurityMasterCapability(
                name="security_master",
                description="SSE official paginated A-share security directory for main board and STAR board",
                supports_pagination=True,
                limitations=[
                    "Official public endpoint candidate; stability, permission and field semantics still require confirmation."
                ],
            )
        ]

    async def health_check(self) -> SecurityMasterResult:
        return await self.list_securities(SecurityMasterQuery(exchanges=["SH"], max_records=2))

    async def list_securities(self, query: SecurityMasterQuery) -> SecurityMasterResult:
        if query.exchanges and "SH" not in {item.upper() for item in query.exchanges}:
            return SecurityMasterResult(
                status=ProviderStatus.DATA_INSUFFICIENT,
                metrics={"endpoint": self.endpoint, "record_count": 0, "exchange_filtered": True},
                provider_metadata={"source_code": self.source_code, "official_domain": "sse.com.cn"},
            )

        max_records = max(1, min(query.max_records, self.settings.security_master_max_records_per_run))
        remaining = max_records
        all_rows: list[dict[str, Any]] = []
        request_count = 0
        success_count = 0
        failure_count = 0
        errors: list[dict[str, str]] = []
        stock_type_totals: dict[str, int | None] = {}

        for stock_type in self.stock_types:
            page_no = 1
            received_for_type = 0
            while remaining > 0:
                page_size = min(1000, remaining)
                response = await provider_http_request(
                    "GET",
                    self.endpoint,
                    params=_params(stock_type=stock_type, page_no=page_no, page_size=page_size),
                    headers={"Referer": "https://www.sse.com.cn/assortment/stock/list/share/"},
                    timeout_seconds=self.settings.security_master_request_timeout_seconds,
                    max_bytes=self.settings.security_master_max_response_bytes,
                )
                request_count += 1
                if not response.ok or not response.text:
                    failure_count += 1
                    errors.append(
                        {
                            "code": response.error_code or str(response.status_code),
                            "summary": f"SSE security list request failed for stockType={stock_type}",
                        }
                    )
                    break

                rows, total = _extract_rows(response.text)
                stock_type_totals[stock_type] = total
                success_count += 1
                if not rows:
                    break
                all_rows.extend(rows)
                received_for_type += len(rows)
                remaining -= len(rows)
                if total is not None and received_for_type >= total:
                    break
                if len(rows) < page_size:
                    break
                page_no += 1

        records = _normalize_rows(self, all_rows)
        if errors and records:
            status = ProviderStatus.PARTIAL
        elif errors:
            status = status_from_http_error(None, errors[0]["code"])
        else:
            status = ProviderStatus.PASS if records else ProviderStatus.DATA_INSUFFICIENT
        return SecurityMasterResult(
            status=status,
            records=records,
            errors=errors,
            metrics={
                "endpoint": self.endpoint,
                "raw_count": len(all_rows),
                "record_count": len(records),
                "stock_type_totals": stock_type_totals,
                "max_records": max_records,
                "truncated_by_max_records": remaining == 0,
            },
            provider_metadata={"source_code": self.source_code, "official_domain": "sse.com.cn"},
            request_count=request_count,
            success_count=success_count,
            failure_count=failure_count,
        )

    def normalize(self, raw_record: dict[str, Any]) -> SecurityMasterRecord:
        code = normalize_code(first_non_empty(raw_record, ["SECURITY_CODE_A", "SECURITY_CODE", "PRODUCTID", "COMPANY_CODE", "code"]))
        if not code:
            raise ValueError("SSE security code missing")
        exchange = "SH"
        short_name = first_non_empty(raw_record, ["SECURITY_ABBR_A", "SECURITY_ABBR", "COMPANY_ABBR", "short_name", "name"])
        security_type = "unsupported_b_share" if code.startswith("900") else normalize_security_type(raw_record.get("security_type"))
        raw_status = first_non_empty(raw_record, ["LIST_STATUS", "LISTING_STATUS", "STATUS", "status"]) or "listed"
        listing_status = normalize_listing_status(raw_status, short_name=short_name)
        board = normalize_board(first_non_empty(raw_record, ["BOARD_NAME", "BOARD", "BOARD_TYPE"]), exchange=exchange, code=code)
        full_name = first_non_empty(raw_record, ["FULL_NAME", "COMPANY_FULL_NAME", "COMPANY_NAME", "full_name"])
        pinyin, initials = pinyin_fields(short_name or "", raw_record)
        normalized = {
            "code": code,
            "exchange": exchange,
            "short_name": short_name,
            "security_type": security_type,
        }
        completeness, missing = completeness_for(normalized, ["code", "exchange", "short_name", "security_type"])
        if not short_name:
            raise ValueError("SSE security name missing")
        return SecurityMasterRecord(
            source_code=self.source_code,
            provider_security_id=str(first_non_empty(raw_record, ["COMPANY_CODE", "SECURITY_CODE_A", "SECURITY_CODE", "PRODUCTID"]) or code),
            symbol=normalize_symbol(code, exchange),
            code=code,
            exchange=exchange,
            market="A_SHARE",
            board=board,
            security_type=security_type,
            short_name=short_name,
            full_name=full_name or short_name,
            english_name=first_non_empty(raw_record, ["ENGLISH_NAME", "english_name"]),
            listing_status=listing_status,
            listed_at=parse_date(first_non_empty(raw_record, ["LISTING_DATE", "LIST_DATE", "LISTDATE"])),
            delisted_at=parse_date(first_non_empty(raw_record, ["DELISTING_DATE", "DELIST_DATE"])),
            previous_symbols=[],
            aliases=_aliases(short_name, full_name, code, exchange),
            raw_metadata_hash=metadata_hash(raw_record),
            fetched_at=fetched_at_now(),
            data_completeness=completeness,
            missing_fields=missing,
            pinyin=pinyin,
            pinyin_initials=initials,
            raw_status=raw_status,
        )


def _params(*, stock_type: str, page_no: int, page_size: int) -> dict[str, str]:
    return {
        "jsonCallBack": "",
        "isPagination": "true",
        "stockType": stock_type,
        "pageHelp.pageSize": str(page_size),
        "pageHelp.pageNo": str(page_no),
        "pageHelp.beginPage": str(page_no),
        "pageHelp.cacheSize": "1",
        "pageHelp.endPage": str(page_no),
    }


def _extract_rows(text: str) -> tuple[list[dict[str, Any]], int | None]:
    payload_text = text.strip().strip("();")
    payload = json.loads(payload_text)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)], None
    if not isinstance(payload, dict):
        return [], None
    page_help = payload.get("pageHelp") if isinstance(payload.get("pageHelp"), dict) else None
    if page_help:
        rows = page_help.get("data")
        total = page_help.get("total")
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else [], _int_or_none(total)
    for key in ("result", "data"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)], None
    return [], None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_rows(provider: SseSecurityMasterProvider, rows: list[dict[str, Any]]) -> list[SecurityMasterRecord]:
    records: list[SecurityMasterRecord] = []
    seen: set[str] = set()
    for row in rows:
        try:
            record = provider.normalize(row)
        except ValueError:
            continue
        if record.security_type == "common_stock" and record.symbol not in seen:
            records.append(record)
            seen.add(record.symbol)
    return records


def _aliases(short_name: str | None, full_name: str | None, code: str, exchange: str) -> list[str]:
    return sorted({value for value in [short_name, full_name, code, f"{code}.{exchange}"] if value})
