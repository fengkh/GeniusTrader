import importlib
import io
from contextlib import redirect_stdout
from datetime import date, timedelta
from typing import Any

from app.core.config import Settings
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
from app.providers.statuses import ProviderStatus


class BaoStockSecurityMasterProvider(SecurityMasterProvider):
    source_code = "BAOSTOCK_DEVELOPMENT_FALLBACK"

    def __init__(self, settings: Settings, module: Any | None = None) -> None:
        self.settings = settings
        self.module = module

    def capabilities(self) -> list[SecurityMasterCapability]:
        return [
            SecurityMasterCapability(
                name="security_master",
                description="BaoStock query_all_stock 开发环境补充来源",
                supports_pagination=False,
                limitations=["BaoStock 不是官方来源，仅可作为开发补充或交叉核验。"],
            )
        ]

    async def health_check(self) -> SecurityMasterResult:
        module = self._module()
        if module is None:
            return _failure("MODULE_NOT_INSTALLED", "baostock package is not installed")
        login_error = _login(module)
        if login_error:
            return _failure("BAOSTOCK_LOGIN_FAILED", login_error)
        _logout(module)
        return SecurityMasterResult(
            status=ProviderStatus.PASS,
            metrics={"adapter": "baostock", "official": False},
            provider_metadata={"source_code": self.source_code, "official": False},
            request_count=1,
            success_count=1,
        )

    async def list_securities(self, query: SecurityMasterQuery) -> SecurityMasterResult:
        module = self._module()
        if module is None:
            return _failure("MODULE_NOT_INSTALLED", "baostock package is not installed")
        login_error = _login(module)
        if login_error:
            return _failure("BAOSTOCK_LOGIN_FAILED", login_error)
        try:
            rows, data_date, attempts = _query_recent_all_stock(module)
        except Exception as exc:  # noqa: BLE001
            return _failure("BAOSTOCK_QUERY_FAILED", exc.__class__.__name__)
        finally:
            _logout(module)
        records = _normalize_rows(self, rows, query=query)
        status = ProviderStatus.PASS if records else ProviderStatus.DATA_INSUFFICIENT
        return SecurityMasterResult(
            status=status,
            records=records,
            metrics={
                "raw_count": len(rows),
                "record_count": len(records),
                "official": False,
                "data_date": data_date,
                "date_attempts": attempts,
            },
            provider_metadata={"source_code": self.source_code, "official": False, "data_date": data_date},
            request_count=1,
            success_count=1,
        )

    def normalize(self, raw_record: dict[str, Any]) -> SecurityMasterRecord:
        provider_code = first_non_empty(raw_record, ["code", "证券代码"])
        exchange = _exchange_from_baostock_code(provider_code) or normalize_exchange(raw_record.get("exchange"))
        code = normalize_code(provider_code)
        if not code or not exchange:
            raise ValueError("BaoStock security code missing")
        short_name = first_non_empty(raw_record, ["code_name", "证券名称", "name"])
        security_type = _security_type_from_code(code, exchange, raw_record)
        listing_status = normalize_listing_status(first_non_empty(raw_record, ["tradeStatus", "list_status", "status"]), short_name=short_name)
        board = normalize_board(first_non_empty(raw_record, ["board", "板块"]), exchange=exchange, code=code)
        pinyin, initials = pinyin_fields(short_name or "", raw_record)
        normalized = {
            "code": code,
            "exchange": exchange,
            "short_name": short_name,
            "security_type": security_type,
        }
        completeness, missing = completeness_for(normalized, ["code", "exchange", "short_name", "security_type"])
        if not short_name:
            raise ValueError("BaoStock security name missing")
        return SecurityMasterRecord(
            source_code=self.source_code,
            provider_security_id=str(provider_code or normalize_symbol(code, exchange)),
            symbol=normalize_symbol(code, exchange),
            code=code,
            exchange=exchange,
            market="A_SHARE",
            board=board,
            security_type=security_type,
            short_name=short_name,
            full_name=first_non_empty(raw_record, ["full_name", "公司全称"]) or short_name,
            english_name=first_non_empty(raw_record, ["english_name"]),
            listing_status=listing_status,
            listed_at=parse_date(first_non_empty(raw_record, ["ipoDate", "list_date", "上市日期"])),
            delisted_at=parse_date(first_non_empty(raw_record, ["outDate", "delist_date", "退市日期"])),
            previous_symbols=[],
            aliases=sorted({short_name}),
            raw_metadata_hash=metadata_hash(raw_record),
            fetched_at=fetched_at_now(),
            data_completeness=completeness,
            missing_fields=missing,
            pinyin=pinyin,
            pinyin_initials=initials,
            raw_status=first_non_empty(raw_record, ["tradeStatus", "list_status", "status"]),
        )

    def _module(self) -> Any | None:
        if self.module is not None:
            return self.module
        try:
            return importlib.import_module("baostock")
        except ModuleNotFoundError:
            return None


def _rows_from_baostock_result(result: Any) -> list[dict[str, Any]]:
    error_code = getattr(result, "error_code", "0")
    if str(error_code) != "0":
        error_msg = getattr(result, "error_msg", "")
        raise RuntimeError(f"BaoStock query failed: {error_code} {error_msg}")
    fields = list(getattr(result, "fields", []) or [])
    rows: list[dict[str, Any]] = []
    while result.next():
        values = result.get_row_data()
        rows.append(dict(zip(fields, values, strict=False)))
    return rows


def _query_recent_all_stock(module: Any, *, lookback_days: int = 10) -> tuple[list[dict[str, Any]], str, int]:
    today = date.today()
    last_rows: list[dict[str, Any]] = []
    last_day = today.isoformat()
    for offset in range(lookback_days + 1):
        day = today - timedelta(days=offset)
        raw_result = module.query_all_stock(day=day.isoformat())
        rows = _rows_from_baostock_result(raw_result)
        last_rows = rows
        last_day = day.isoformat()
        if rows:
            return rows, last_day, offset + 1
    return last_rows, last_day, lookback_days + 1


def _exchange_from_baostock_code(value: str | None) -> str | None:
    if not value or "." not in value:
        return None
    prefix = value.split(".", 1)[0].lower()
    return {"sh": "SH", "sz": "SZ", "bj": "BJ"}.get(prefix)


def _security_type_from_code(code: str, exchange: str, raw: dict[str, Any]) -> str:
    if (exchange == "SH" and code.startswith("900")) or (exchange == "SZ" and code.startswith("200")):
        return "unsupported_b_share"
    return normalize_security_type(raw.get("security_type"))


def _login(module: Any) -> str | None:
    try:
        with redirect_stdout(io.StringIO()):
            result = module.login()
    except Exception as exc:  # noqa: BLE001
        return exc.__class__.__name__
    error_code = getattr(result, "error_code", "0")
    if str(error_code) != "0":
        return f"{error_code} {getattr(result, 'error_msg', '')}".strip()
    return None


def _logout(module: Any) -> None:
    if hasattr(module, "logout"):
        with redirect_stdout(io.StringIO()):
            module.logout()


def _failure(code: str, summary: str) -> SecurityMasterResult:
    return SecurityMasterResult(
        status=ProviderStatus.NOT_AVAILABLE if code == "MODULE_NOT_INSTALLED" else ProviderStatus.NETWORK_ERROR,
        errors=[{"code": code, "summary": summary}],
        metrics={"official": False},
        provider_metadata={"source_code": "BAOSTOCK_DEVELOPMENT_FALLBACK", "official": False},
        request_count=1,
        failure_count=1,
    )


def _normalize_rows(
    provider: BaoStockSecurityMasterProvider,
    rows: list[dict[str, Any]],
    *,
    query: SecurityMasterQuery,
) -> list[SecurityMasterRecord]:
    records: list[SecurityMasterRecord] = []
    allowed_exchanges = {value.upper() for value in query.exchanges if value.strip()}
    for row in rows:
        try:
            record = provider.normalize(row)
        except ValueError:
            continue
        if allowed_exchanges and record.exchange not in allowed_exchanges:
            continue
        if record.security_type == "common_stock":
            records.append(record)
        if len(records) >= query.max_records:
            break
    return records
