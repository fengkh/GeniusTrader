import asyncio
import contextlib
import io
from datetime import date, timedelta
from typing import Any

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.time import utc_now
from app.providers.market_data.base import (
    MarketDataProvider,
    provider_error,
    with_redacted_metadata,
)
from app.providers.market_data.models import (
    DailyMarketSnapshotRecord,
    MarketDataProviderResult,
    MarketDataQuery,
    TradeCalendarDay,
)
from app.providers.market_data.normalization import (
    decimal_or_none,
    normalize_symbol,
    parse_trade_date,
    ratio_or_percent_to_percent_number,
    stable_hash,
)
from app.providers.statuses import ProviderStatus

BAOSTOCK_FIELDS = "date,code,open,high,low,close,preclose,volume,amount,pctChg,turn,tradestatus"
BAOSTOCK_REQUIRED_FIELDS = [
    "trade_date",
    "open",
    "close",
    "high",
    "low",
    "volume",
    "amount",
    "pct_change",
    "turnover_rate",
]


class BaoStockMarketDataProvider(MarketDataProvider):
    source_code = "BAOSTOCK"
    provider_adapter = "baostock.query_history_k_data_plus"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def capabilities(self) -> list[str]:
        return ["daily_snapshot", "trade_calendar", "cross_check"]

    async def health_check(self) -> MarketDataProviderResult:
        self._ensure_configured_and_allowed()
        return MarketDataProviderResult(
            status=ProviderStatus.PASS,
            provider_metadata=self._metadata({"network": False}),
            request_count=0,
            success_count=1,
        )

    async def trade_calendar(self, query: MarketDataQuery) -> list[TradeCalendarDay]:
        self._ensure_configured_and_allowed()
        date_to = query.date_to or query.trade_date or utc_now().date()
        date_from = query.date_from or date_to - timedelta(days=25)
        result = await self.fetch_daily_snapshots(
            MarketDataQuery(
                trade_date=date_to,
                date_from=date_from,
                date_to=date_to,
                symbols=["600519.SH", "300750.SZ"],
                max_records=2,
                mode=query.mode,
                dry_run=True,
            )
        )
        dates = sorted({record.trade_date for record in result.records if date_from <= record.trade_date <= date_to})
        return _calendar_days(dates, source_code=self.source_code)

    async def fetch_daily_snapshots(self, query: MarketDataQuery) -> MarketDataProviderResult:
        self._ensure_configured_and_allowed()
        if not query.trade_date:
            return MarketDataProviderResult(
                status=ProviderStatus.DATA_INSUFFICIENT,
                errors=[provider_error("TRADE_DATE_REQUIRED", "trade_date is required")],
                provider_metadata=self._metadata({}),
            )
        records: list[DailyMarketSnapshotRecord] = []
        errors: list[dict[str, str]] = []
        request_count = 0
        for symbol in [normalize_symbol(item) for item in query.symbols[: query.max_records]]:
            if symbol.endswith(".BJ"):
                errors.append(provider_error("BAOSTOCK_BJ_UNVERIFIED", f"{symbol} is unsupported until verified"))
                continue
            if request_count:
                await asyncio.sleep(0.2)
            request_count += 1
            try:
                rows = await self._query_history(symbol=symbol, target_date=query.trade_date)
                record = self._normalize_record(symbol=symbol, target_date=query.trade_date, rows=rows)
            except AppError as exc:
                errors.append(provider_error(exc.code.value, exc.message))
                continue
            if record is None:
                errors.append(provider_error("NO_TARGET_TRADE_DATE", f"{symbol} has no BaoStock row for target date"))
                continue
            records.append(record)
        status = ProviderStatus.PASS if records and not errors else ProviderStatus.PARTIAL if records else ProviderStatus.DATA_INSUFFICIENT
        result = MarketDataProviderResult(
            status=status,
            records=records,
            errors=errors,
            metrics={
                "requested_symbol_count": len(query.symbols[: query.max_records]),
                "raw_units": {"volume": "share", "amount": "CNY"},
                "normalized_units": {"volume": "share", "amount": "CNY"},
                "provider_limitations": ["BJ support is unverified and not requested by this adapter."],
            },
            provider_metadata=self._metadata({"network": True}),
            request_count=request_count,
            success_count=len(records),
            failure_count=max(0, len(query.symbols[: query.max_records]) - len(records)),
        )
        return with_redacted_metadata(result)

    async def _query_history(self, *, symbol: str, target_date: date) -> list[dict[str, Any]]:
        start_date = (target_date - timedelta(days=15)).isoformat()
        end_date = target_date.isoformat()
        baostock_symbol = _to_baostock_symbol(symbol)
        return await asyncio.wait_for(
            asyncio.to_thread(
                self._query_history_blocking,
                baostock_symbol=baostock_symbol,
                start_date=start_date,
                end_date=end_date,
            ),
            timeout=self.settings.market_data_request_timeout_seconds,
        )

    def _query_history_blocking(self, *, baostock_symbol: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
        bs = self._load_baostock()
        with contextlib.redirect_stdout(io.StringIO()):
            login = bs.login()
            try:
                if getattr(login, "error_code", "0") != "0":
                    raise AppError(ErrorCode.MARKET_DATA_SYNC_FAILED, "BaoStock login failed", status_code=502)
                result = bs.query_history_k_data_plus(
                    baostock_symbol,
                    BAOSTOCK_FIELDS,
                    start_date=start_date,
                    end_date=end_date,
                    frequency="d",
                    adjustflag="3",
                )
                if getattr(result, "error_code", "0") != "0":
                    raise AppError(ErrorCode.MARKET_DATA_SYNC_FAILED, "BaoStock query failed", status_code=502)
                fields = [str(field) for field in getattr(result, "fields", [])]
                rows: list[dict[str, Any]] = []
                while result.next():
                    rows.append(dict(zip(fields, result.get_row_data(), strict=False)))
                return rows
            finally:
                try:
                    bs.logout()
                except Exception:
                    pass

    def _normalize_record(
        self,
        *,
        symbol: str,
        target_date: date,
        rows: list[dict[str, Any]],
    ) -> DailyMarketSnapshotRecord | None:
        ordered = sorted(rows, key=lambda item: parse_trade_date(item.get("date")) or date.min)
        target: dict[str, Any] | None = None
        for row in ordered:
            if parse_trade_date(row.get("date")) == target_date:
                target = row
                break
        if target is None:
            return None
        trade_date = parse_trade_date(target.get("date"))
        values = {
            "trade_date": trade_date,
            "open": decimal_or_none(target.get("open")),
            "close": decimal_or_none(target.get("close")),
            "high": decimal_or_none(target.get("high")),
            "low": decimal_or_none(target.get("low")),
            "volume": decimal_or_none(target.get("volume")),
            "amount": decimal_or_none(target.get("amount")),
            "pct_change": decimal_or_none(target.get("pctChg")),
            "turnover_rate": ratio_or_percent_to_percent_number(target.get("turn")),
        }
        pre_close = decimal_or_none(target.get("preclose"))
        change = values["close"] - pre_close if values["close"] is not None and pre_close is not None else None
        missing = [field for field in BAOSTOCK_REQUIRED_FIELDS if values[field] is None]
        completeness = "complete" if not missing else "partial" if values["trade_date"] and values["close"] else "insufficient"
        fetched_at = utc_now()
        return DailyMarketSnapshotRecord(
            source_code=self.source_code,
            symbol=symbol,
            trade_date=trade_date or target_date,
            open=values["open"],
            high=values["high"],
            low=values["low"],
            close=values["close"],
            pre_close=pre_close,
            change=change,
            pct_change=values["pct_change"],
            volume=values["volume"],
            amount=values["amount"],
            turnover_rate=values["turnover_rate"],
            volume_ratio=None,
            total_market_value=None,
            circulating_market_value=None,
            pe_ttm=None,
            pb=None,
            is_trading=target.get("tradestatus") in {"1", 1, None},
            data_completeness=completeness,
            source_updated_at=fetched_at,
            fetched_at=fetched_at,
            raw_metadata_hash=stable_hash(
                {
                    "source_code": self.source_code,
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "open": target.get("open"),
                    "close": target.get("close"),
                    "volume": target.get("volume"),
                    "amount": target.get("amount"),
                }
            ),
            limitations=[
                "BaoStock is an explicit development cross-check source, not an official or production-authorized feed.",
                "BJ support remains unverified; this adapter does not claim BJ coverage.",
                *[f"missing_field:{field}" for field in missing],
            ],
            source_record_ref=f"{self.source_code}:{symbol}:{trade_date or target_date}",
        )

    @staticmethod
    def _load_baostock() -> Any:
        try:
            import baostock as bs  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AppError(
                ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED,
                "baostock is not installed in the backend environment",
                status_code=503,
            ) from exc
        return bs

    def _ensure_configured_and_allowed(self) -> None:
        if self.settings.is_production:
            raise AppError(
                ErrorCode.MARKET_DATA_PERMISSION_DENIED,
                "BaoStock is unverified and disabled for production",
                status_code=403,
            )
        if not self.settings.market_data_provider_enabled or not self.settings.market_data_baostock_enabled:
            raise AppError(
                ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED,
                "BaoStock market data provider is not enabled",
                status_code=503,
            )
        if not self.settings.market_data_real_network_enabled:
            raise AppError(
                ErrorCode.MARKET_DATA_REAL_NETWORK_DISABLED,
                "Real market data networking is disabled",
                status_code=403,
            )

    def _metadata(self, extra: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_code": self.source_code,
            "source_name": "BaoStock A-share Daily",
            "source_type": "third_party_data_service",
            "authorization_status": "unverified",
            "usage_scope": ["local_development", "internal_testing"],
            "production_enabled": False,
            "is_official": False,
            **extra,
        }


def _to_baostock_symbol(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    code, exchange = normalized.split(".", 1)
    if exchange == "SH":
        return f"sh.{code}"
    if exchange == "SZ":
        return f"sz.{code}"
    raise AppError(ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED, f"{symbol} is unsupported by BaoStock adapter", status_code=422)


def _calendar_days(open_dates: list[date], *, source_code: str) -> list[TradeCalendarDay]:
    previous: date | None = None
    rows: list[TradeCalendarDay] = []
    for trade_date in open_dates:
        rows.append(
            TradeCalendarDay(
                trade_date=trade_date,
                is_open=True,
                previous_open_date=previous,
                source_code=source_code,
            )
        )
        previous = trade_date
    return rows
