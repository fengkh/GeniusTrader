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


class SzseSecurityMasterProvider(SecurityMasterProvider):
    source_code = "SZSE_SECURITY_MASTER"
    endpoint = "https://www.szse.cn/api/report/ShowReport"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def capabilities(self) -> list[SecurityMasterCapability]:
        return [
            SecurityMasterCapability(
                name="security_master",
                description="深交所体系公开证券目录小样本同步",
                supports_pagination=True,
                limitations=["深交所证券目录接口稳定性和字段口径仍需真实数据阶段确认。"],
            )
        ]

    async def health_check(self) -> SecurityMasterResult:
        return await self.list_securities(SecurityMasterQuery(exchanges=["SZ"], max_records=1))

    async def list_securities(self, query: SecurityMasterQuery) -> SecurityMasterResult:
        params = {
            "SHOWTYPE": "JSON",
            "CATALOGID": "1110",
            "TABKEY": "tab1",
            "PAGENO": "1",
            "PAGESIZE": str(max(1, min(query.max_records, self.settings.security_master_max_records_per_run))),
            "random": "0.123456789",
        }
        response = await provider_http_request(
            "GET",
            self.endpoint,
            params=params,
            headers={"Referer": "https://www.szse.cn/market/product/stock/list/index.html"},
            timeout_seconds=self.settings.security_master_request_timeout_seconds,
            max_bytes=self.settings.security_master_max_response_bytes,
        )
        if not response.ok or not response.text:
            status = status_from_http_error(response.status_code, response.error_code)
            return SecurityMasterResult(
                status=status,
                errors=[{"code": response.error_code or str(response.status_code), "summary": "SZSE security list request failed"}],
                metrics={"endpoint": self.endpoint, "response_bytes": response.response_bytes},
                request_count=1,
                failure_count=1,
            )
        rows = _extract_rows(response.text)
        records = _normalize_rows(self, rows)
        status = ProviderStatus.PASS if records else ProviderStatus.DATA_INSUFFICIENT
        return SecurityMasterResult(
            status=status,
            records=records,
            metrics={"endpoint": self.endpoint, "raw_count": len(rows), "record_count": len(records)},
            provider_metadata={"source_code": self.source_code, "official_domain": "szse.cn"},
            request_count=1,
            success_count=1,
        )

    def normalize(self, raw_record: dict[str, Any]) -> SecurityMasterRecord:
        code = normalize_code(first_non_empty(raw_record, ["agdm", "zqdm", "secCode", "A股代码", "证券代码", "code"]))
        if not code:
            raise ValueError("SZSE security code missing")
        exchange = "SZ"
        short_name = first_non_empty(raw_record, ["agjc", "zqjc", "secName", "A股简称", "证券简称", "name"])
        security_type = "unsupported_b_share" if code.startswith("200") else normalize_security_type(raw_record.get("security_type"))
        raw_status = first_non_empty(raw_record, ["zt", "status", "上市状态"]) or "上市"
        listing_status = normalize_listing_status(raw_status, short_name=short_name)
        board = normalize_board(first_non_empty(raw_record, ["bk", "plate", "板块", "板块名称"]), exchange=exchange, code=code)
        full_name = first_non_empty(raw_record, ["gsmc", "gsqc", "companyName", "公司全称", "full_name"])
        pinyin, initials = pinyin_fields(short_name or "", raw_record)
        normalized = {
            "code": code,
            "exchange": exchange,
            "short_name": short_name,
            "security_type": security_type,
        }
        completeness, missing = completeness_for(normalized, ["code", "exchange", "short_name", "security_type"])
        if not short_name:
            raise ValueError("SZSE security name missing")
        return SecurityMasterRecord(
            source_code=self.source_code,
            provider_security_id=str(first_non_empty(raw_record, ["agdm", "zqdm", "secCode", "证券代码"]) or code),
            symbol=normalize_symbol(code, exchange),
            code=code,
            exchange=exchange,
            market="A_SHARE",
            board=board,
            security_type=security_type,
            short_name=short_name,
            full_name=full_name or short_name,
            english_name=first_non_empty(raw_record, ["ywmc", "englishName", "english_name"]),
            listing_status=listing_status,
            listed_at=parse_date(first_non_empty(raw_record, ["agssrq", "ssrq", "listingDate", "上市日期"])),
            delisted_at=parse_date(first_non_empty(raw_record, ["zzssrq", "delistingDate", "退市日期"])),
            previous_symbols=[],
            aliases=_aliases(short_name, full_name),
            raw_metadata_hash=metadata_hash(raw_record),
            fetched_at=fetched_at_now(),
            data_completeness=completeness,
            missing_fields=missing,
            pinyin=pinyin,
            pinyin_initials=initials,
            raw_status=raw_status,
        )


def _extract_rows(text: str) -> list[dict[str, Any]]:
    payload = json.loads(text.strip())
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        if data and isinstance(data[0], dict) and isinstance(data[0].get("data"), list):
            return [row for group in data for row in group.get("data", []) if isinstance(row, dict)]
        return [row for row in data if isinstance(row, dict)]
    rows = payload.get("rows") or payload.get("result")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _normalize_rows(provider: SzseSecurityMasterProvider, rows: list[dict[str, Any]]) -> list[SecurityMasterRecord]:
    records: list[SecurityMasterRecord] = []
    for row in rows:
        try:
            record = provider.normalize(row)
        except ValueError:
            continue
        if record.security_type == "common_stock":
            records.append(record)
    return records


def _aliases(short_name: str | None, full_name: str | None) -> list[str]:
    return sorted({value for value in [short_name, full_name] if value})
