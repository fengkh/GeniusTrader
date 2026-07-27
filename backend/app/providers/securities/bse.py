import re
from html import unescape
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
    normalize_exchange,
    normalize_listing_status,
    normalize_security_type,
    normalize_symbol,
    parse_date,
    pinyin_fields,
)
from app.providers.statuses import ProviderStatus, status_from_http_error


class BseSecurityMasterProvider(SecurityMasterProvider):
    source_code = "BSE_SECURITY_MASTER"
    page_url = "https://www.bse.cn/nq/listedcompany.html"
    code_mapping_url = "https://www.bse.cn/service/code_mapping.html"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def capabilities(self) -> list[SecurityMasterCapability]:
        return [
            SecurityMasterCapability(
                name="security_master",
                description="BSE official code mapping page for current 920-prefixed securities",
                supports_pagination=False,
                limitations=[
                    "Uses the official BSE code mapping page; it verifies current BJ code identity, not real-time quotes."
                ],
            )
        ]

    async def health_check(self) -> SecurityMasterResult:
        return await self.list_securities(SecurityMasterQuery(exchanges=["BJ"], max_records=1))

    async def list_securities(self, query: SecurityMasterQuery) -> SecurityMasterResult:
        response = await provider_http_request(
            "GET",
            self.code_mapping_url,
            headers={"Referer": self.page_url},
            timeout_seconds=self.settings.security_master_request_timeout_seconds,
            max_bytes=self.settings.security_master_max_response_bytes,
        )
        if not response.ok or not response.text:
            status = status_from_http_error(response.status_code, response.error_code)
            return SecurityMasterResult(
                status=status,
                errors=[
                    {
                        "code": response.error_code or str(response.status_code),
                        "summary": "BSE code mapping page request failed",
                    }
                ],
                metrics={"page_url": self.code_mapping_url, "response_bytes": response.response_bytes},
                request_count=1,
                failure_count=1,
            )

        rows = _extract_rows(response.text, limit=query.max_records)
        records = _normalize_rows(self, rows)
        status = ProviderStatus.PASS if records else ProviderStatus.DATA_INSUFFICIENT
        errors = [] if records else [{"code": "DATA_INSUFFICIENT", "summary": "BSE code mapping page had no stable rows"}]
        return SecurityMasterResult(
            status=status,
            records=records,
            errors=errors,
            metrics={"page_url": self.code_mapping_url, "raw_count": len(rows), "record_count": len(records)},
            provider_metadata={"source_code": self.source_code, "official_domain": "bse.cn"},
            request_count=1,
            success_count=1,
        )

    def normalize(self, raw_record: dict[str, Any]) -> SecurityMasterRecord:
        code = normalize_code(first_non_empty(raw_record, ["new_code", "code", "secuCode"]))
        if not code:
            raise ValueError("BSE security code missing")
        exchange = normalize_exchange(first_non_empty(raw_record, ["exchange"])) or "BJ"
        short_name = first_non_empty(raw_record, ["name", "secuAbbr"])
        security_type = normalize_security_type(raw_record.get("security_type"))
        raw_status = first_non_empty(raw_record, ["status"]) or "listed"
        listing_status = normalize_listing_status(raw_status, short_name=short_name)
        board = normalize_board(first_non_empty(raw_record, ["board"]), exchange=exchange, code=code)
        full_name = first_non_empty(raw_record, ["full_name", "companyName"])
        pinyin, initials = pinyin_fields(short_name or "", raw_record)
        normalized = {
            "code": code,
            "exchange": exchange,
            "short_name": short_name,
            "security_type": security_type,
        }
        completeness, missing = completeness_for(normalized, ["code", "exchange", "short_name", "security_type"])
        if not short_name:
            raise ValueError("BSE security name missing")

        old_code = normalize_code(first_non_empty(raw_record, ["old_code", "previous_code"]))
        previous_symbols = [f"{old_code}.{exchange}", old_code] if old_code and old_code != code else []
        return SecurityMasterRecord(
            source_code=self.source_code,
            provider_security_id=str(first_non_empty(raw_record, ["provider_security_id", "new_code", "code"]) or code),
            symbol=normalize_symbol(code, exchange),
            code=code,
            exchange=exchange,
            market="A_SHARE",
            board=board,
            security_type=security_type,
            short_name=short_name,
            full_name=full_name or short_name,
            english_name=first_non_empty(raw_record, ["english_name"]),
            listing_status=listing_status,
            listed_at=parse_date(first_non_empty(raw_record, ["listed_at", "list_date"])),
            delisted_at=parse_date(first_non_empty(raw_record, ["delisted_at"])),
            previous_symbols=previous_symbols,
            aliases=_aliases(short_name, full_name, old_code, code, exchange),
            raw_metadata_hash=metadata_hash(raw_record),
            fetched_at=fetched_at_now(),
            data_completeness=completeness,
            missing_fields=missing,
            pinyin=pinyin,
            pinyin_initials=initials,
            raw_status=raw_status,
        )


def _extract_rows(text: str, *, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cells in _table_cells(text):
        if len(cells) < 5 or not cells[0].isdigit():
            continue
        old_code = normalize_code(cells[3])
        new_code = normalize_code(cells[4])
        if not new_code or not new_code.startswith("920"):
            continue
        rows.append(
            {
                "name": cells[1],
                "list_date": cells[2],
                "old_code": old_code,
                "new_code": new_code,
                "exchange": "BJ",
                "status": "listed",
                "security_type": "common_stock",
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _table_cells(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw_row in re.findall(r"<tr[\s\S]*?</tr>", text, flags=re.IGNORECASE):
        cells = [
            _clean_html(cell)
            for cell in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", raw_row, flags=re.IGNORECASE)
        ]
        if cells:
            rows.append(cells)
    return rows


def _clean_html(value: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", value)).strip()


def _normalize_rows(provider: BseSecurityMasterProvider, rows: list[dict[str, Any]]) -> list[SecurityMasterRecord]:
    records: list[SecurityMasterRecord] = []
    for row in rows:
        try:
            record = provider.normalize(row)
        except ValueError:
            continue
        if record.security_type == "common_stock":
            records.append(record)
    return records


def _aliases(short_name: str | None, full_name: str | None, old_code: str | None, code: str, exchange: str) -> list[str]:
    values = {short_name, full_name, code, f"{code}.{exchange}"}
    if old_code:
        values.update({old_code, f"{old_code}.{exchange}"})
    return sorted(value for value in values if value)
