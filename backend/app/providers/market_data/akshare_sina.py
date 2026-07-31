import asyncio
from collections.abc import Iterable
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from time import perf_counter
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

SINA_REQUIRED_FIELDS = ["trade_date", "open", "close", "high", "low", "volume", "amount"]
SINA_MAX_NETWORK_ATTEMPTS = 2
SINA_RETRY_BACKOFF_SECONDS = (2,)
RETRYABLE_SANITIZED_ERROR_TYPES = {"ProxyError", "ConnectTimeout", "ReadTimeout", "ConnectionError"}
RAW_UNITS = {
    "volume": "share",
    "amount": "CNY",
    "turnover_rate": "ratio_or_percent_number",
}
NORMALIZED_UNITS = {
    "volume": "share",
    "amount": "CNY",
    "pct_change": "percent_number",
    "turnover_rate": "percent_number",
}


class AkShareSinaDailyMarketDataProvider(MarketDataProvider):
    source_code = "AKSHARE_SINA_DAILY"
    provider_adapter = "akshare.stock_zh_a_daily"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._stage_events: list[dict[str, Any]] = []
        self._attempt_counts: dict[str, int] = {}

    def capabilities(self) -> list[str]:
        return ["daily_snapshot", "trade_calendar"]

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
                symbols=["920000.BJ"],
                max_records=1,
                mode=query.mode,
                dry_run=True,
            )
        )
        dates = sorted({record.trade_date for record in result.records if date_from <= record.trade_date <= date_to})
        return _calendar_days(dates, source_code=self.source_code)

    async def fetch_daily_snapshots(self, query: MarketDataQuery) -> MarketDataProviderResult:
        self._ensure_configured_and_allowed()
        self._stage_events = []
        self._attempt_counts = {}
        if not query.trade_date:
            return MarketDataProviderResult(
                status=ProviderStatus.DATA_INSUFFICIENT,
                errors=[provider_error("TRADE_DATE_REQUIRED", "trade_date is required")],
                provider_metadata=self._metadata({}),
            )
        symbols = [normalize_symbol(symbol) for symbol in query.symbols[: query.max_records]]
        records: list[DailyMarketSnapshotRecord] = []
        errors: list[dict[str, str]] = []
        latest_available_dates: dict[str, str] = {}
        request_count = 0
        for symbol in symbols:
            if not symbol.endswith(".BJ"):
                errors.append(provider_error("AKSHARE_SINA_NON_BJ_UNSUPPORTED", f"{symbol} is outside BJ route"))
                continue
            if request_count:
                await asyncio.sleep(0.2)
            request_count += 1
            self._record_stage("stock_fetch_started", symbol=symbol, trade_date=query.trade_date)
            rows: list[dict[str, Any]] = []
            try:
                rows = await self._stock_rows(symbol=symbol, target_date=query.trade_date, date_from=query.date_from)
                record = self._normalize_record(symbol=symbol, target_date=query.trade_date, rows=rows)
            except AppError as exc:
                self._record_stage(
                    "normalization_failed" if exc.code == ErrorCode.MARKET_DATA_SOURCE_CHANGED else "stock_fetch_failed",
                    symbol=symbol,
                    trade_date=query.trade_date,
                    sanitized_error_code=exc.code.value,
                    sanitized_error_type=_sanitized_app_error_type(exc),
                )
                errors.append(provider_error(exc.code.value, exc.message))
                continue
            latest_available = _latest_trade_date(rows)
            if latest_available:
                latest_available_dates[symbol] = latest_available.isoformat()
            if record is None:
                source_lag = latest_available is not None and latest_available < query.trade_date
                code = "SOURCE_LAG" if source_lag else "NO_TARGET_TRADE_DATE"
                summary = (
                    f"{symbol} latest available date {latest_available.isoformat()} lags target {query.trade_date}"
                    if source_lag and latest_available
                    else f"{symbol} has no AKShare Sina row for target trade date"
                )
                self._record_stage(
                    "normalization_failed",
                    symbol=symbol,
                    trade_date=query.trade_date,
                    sanitized_error_code=code,
                    sanitized_error_type="DataInsufficient",
                )
                errors.append(provider_error(code, summary))
                continue
            self._record_stage("stock_fetch_succeeded", symbol=symbol, trade_date=query.trade_date)
            self._record_stage("normalization_succeeded", symbol=symbol, trade_date=query.trade_date)
            records.append(record)

        status = _result_status(records=records, errors=errors, requested_count=len(symbols))
        result = MarketDataProviderResult(
            status=status,
            records=records,
            errors=errors,
            metrics={
                "requested_symbol_count": len(symbols),
                "available_fields": _available_fields(records),
                "missing_fields": _missing_fields(records),
                "raw_units": RAW_UNITS,
                "normalized_units": NORMALIZED_UNITS,
                "volume_multiplier": 1,
                "amount_multiplier": 1,
                "turnover_normalization": "ratio_values_under_0.1_are_multiplied_by_100",
                "latest_available_trade_dates": latest_available_dates,
                "freshness_status": "source_lag" if any(error.get("code") == "SOURCE_LAG" for error in errors) else None,
                "attempt_counts": dict(self._attempt_counts),
                "stage_events": self._stage_events,
            },
            provider_metadata=self._metadata({"network": True}),
            request_count=request_count,
            success_count=len(records),
            failure_count=max(0, len(symbols) - len(records)),
        )
        return with_redacted_metadata(result)

    async def _stock_rows(self, *, symbol: str, target_date: date, date_from: date | None) -> list[dict[str, Any]]:
        provider_symbol = _to_sina_symbol(symbol)
        start_date = (date_from or target_date - timedelta(days=15)).strftime("%Y%m%d")
        end_date = target_date.strftime("%Y%m%d")
        data = await self._call_akshare(
            "stock_zh_a_daily",
            event_stage="stock_fetch",
            event_symbol=symbol,
            event_trade_date=target_date,
            symbol=provider_symbol,
            start_date=start_date,
            end_date=end_date,
            adjust="",
        )
        return _dataframe_rows(data)

    def _normalize_record(
        self,
        *,
        symbol: str,
        target_date: date,
        rows: list[dict[str, Any]],
    ) -> DailyMarketSnapshotRecord | None:
        ordered = sorted(rows, key=lambda item: _row_trade_date(item) or date.min)
        target_index: int | None = None
        for index, row in enumerate(ordered):
            if _row_trade_date(row) == target_date:
                target_index = index
                break
        if target_index is None:
            return None
        row = ordered[target_index]
        previous_row = ordered[target_index - 1] if target_index > 0 else None
        trade_date = _row_trade_date(row)
        close = _quantize(decimal_or_none(row.get("close")), "0.000001")
        pre_close = _quantize(decimal_or_none(previous_row.get("close")) if previous_row else None, "0.000001")
        change = _quantize(close - pre_close if close is not None and pre_close is not None else None, "0.000001")
        pct_change = _pct_change(close=close, pre_close=pre_close)
        values = {
            "trade_date": trade_date,
            "open": _quantize(decimal_or_none(row.get("open")), "0.000001"),
            "close": close,
            "high": _quantize(decimal_or_none(row.get("high")), "0.000001"),
            "low": _quantize(decimal_or_none(row.get("low")), "0.000001"),
            "volume": _quantize(decimal_or_none(row.get("volume")), "0.0001"),
            "amount": _quantize(decimal_or_none(row.get("amount")), "0.0001"),
        }
        missing_required = [field for field in SINA_REQUIRED_FIELDS if values[field] is None]
        completeness = "complete" if not missing_required else "partial" if values["trade_date"] and values["close"] else "insufficient"
        fetched_at = utc_now()
        return DailyMarketSnapshotRecord(
            source_code=self.source_code,
            symbol=symbol,
            trade_date=trade_date or target_date,
            open=values["open"],
            high=values["high"],
            low=values["low"],
            close=close,
            pre_close=pre_close,
            change=change,
            pct_change=pct_change,
            volume=values["volume"],
            amount=values["amount"],
            turnover_rate=_quantize(ratio_or_percent_to_percent_number(row.get("turnover")), "0.000001"),
            volume_ratio=None,
            total_market_value=None,
            circulating_market_value=None,
            pe_ttm=None,
            pb=None,
            is_trading=close is not None,
            data_completeness=completeness,
            source_updated_at=fetched_at,
            fetched_at=fetched_at,
            raw_metadata_hash=stable_hash(
                {
                    "source_code": self.source_code,
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "open": row.get("open"),
                    "close": row.get("close"),
                    "volume": row.get("volume"),
                    "amount": row.get("amount"),
                }
            ),
            limitations=[
                "AKShare Sina daily is an unverified BJ low-frequency candidate, not official, realtime, or production-authorized.",
                "Missing market value and valuation fields are kept null; AI never fills them.",
                *[f"missing_field:{field}" for field in missing_required],
                *[f"missing_field:{field}" for field in ["total_market_value", "circulating_market_value", "pe_ttm", "pb", "volume_ratio"]],
            ],
            source_record_ref=f"{self.source_code}:{symbol}:{trade_date or target_date}",
        )

    async def _call_akshare(
        self,
        func_name: str,
        *,
        event_stage: str,
        event_symbol: str | None = None,
        event_trade_date: date | None = None,
        **kwargs: Any,
    ) -> Any:
        module = self._load_akshare()
        func = getattr(module, func_name, None)
        if func is None:
            raise AppError(
                ErrorCode.MARKET_DATA_SOURCE_CHANGED,
                f"AKShare function {func_name} is unavailable",
                status_code=502,
            )
        for attempt in range(1, SINA_MAX_NETWORK_ATTEMPTS + 1):
            started = perf_counter()
            try:
                value = await asyncio.wait_for(
                    asyncio.to_thread(func, **kwargs),
                    timeout=self.settings.market_data_request_timeout_seconds,
                )
                self._remember_attempt(event_symbol, attempt)
                return value
            except Exception as exc:
                duration_ms = int((perf_counter() - started) * 1000)
                sanitized_type = _sanitized_network_error_type(exc)
                self._remember_attempt(event_symbol, attempt)
                self._record_stage(
                    f"{event_stage}_failed",
                    symbol=event_symbol,
                    trade_date=event_trade_date,
                    attempt=attempt,
                    duration_ms=duration_ms,
                    sanitized_error_code=ErrorCode.MARKET_DATA_SYNC_FAILED.value,
                    sanitized_error_type=sanitized_type,
                )
                if sanitized_type in RETRYABLE_SANITIZED_ERROR_TYPES and attempt < SINA_MAX_NETWORK_ATTEMPTS:
                    await asyncio.sleep(SINA_RETRY_BACKOFF_SECONDS[attempt - 1])
                    continue
                raise AppError(
                    ErrorCode.MARKET_DATA_SYNC_FAILED,
                    f"AKShare Sina request failed: {sanitized_type}",
                    status_code=504 if sanitized_type in {"ConnectTimeout", "ReadTimeout"} else 502,
                ) from exc

    @staticmethod
    def _load_akshare() -> Any:
        try:
            import akshare as ak  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AppError(
                ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED,
                "akshare is not installed in the backend environment",
                status_code=503,
            ) from exc
        return ak

    def _ensure_configured_and_allowed(self) -> None:
        if self.settings.is_production:
            raise AppError(
                ErrorCode.MARKET_DATA_PERMISSION_DENIED,
                "AKShare Sina daily is unverified and disabled for production",
                status_code=403,
            )
        if not self.settings.market_data_provider_enabled or not self.settings.market_data_akshare_sina_enabled:
            raise AppError(
                ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED,
                "AKShare Sina daily market data provider is not enabled",
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
            "source_name": "AKShare / Sina A-share Daily",
            "source_type": "third_party_data_service",
            "authorization_status": "unverified",
            "usage_scope": ["local_development", "internal_testing"],
            "production_enabled": False,
            "is_official": False,
            "raw_units": RAW_UNITS,
            "normalized_units": NORMALIZED_UNITS,
            **extra,
        }

    def _record_stage(
        self,
        stage: str,
        *,
        symbol: str | None = None,
        trade_date: date | None = None,
        attempt: int | None = None,
        duration_ms: int | None = None,
        sanitized_error_code: str | None = None,
        sanitized_error_type: str | None = None,
    ) -> None:
        event = {
            key: value
            for key, value in {
                "provider_code": self.source_code,
                "symbol": symbol,
                "trade_date": trade_date.isoformat() if trade_date else None,
                "stage": stage,
                "attempt": attempt,
                "duration_ms": duration_ms,
                "sanitized_error_code": sanitized_error_code,
                "sanitized_error_type": sanitized_error_type,
            }.items()
            if value is not None
        }
        self._stage_events.append(event)

    def _remember_attempt(self, symbol: str | None, attempt: int) -> None:
        if symbol:
            self._attempt_counts[symbol] = max(self._attempt_counts.get(symbol, 0), attempt)


def _to_sina_symbol(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    code, exchange = normalized.split(".", 1)
    if exchange == "BJ":
        return f"bj{code}"
    raise AppError(
        ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED,
        f"{symbol} is unsupported by AKShare Sina daily adapter",
        status_code=422,
    )


def _row_trade_date(row: dict[str, Any]) -> date | None:
    return parse_trade_date(row.get("date") or row.get("日期") or row.get("index"))


def _latest_trade_date(rows: list[dict[str, Any]]) -> date | None:
    dates = [_row_trade_date(row) for row in rows]
    return max((item for item in dates if item is not None), default=None)


def _pct_change(*, close: Decimal | None, pre_close: Decimal | None) -> Decimal | None:
    if close is None or pre_close in {None, Decimal("0")}:
        return None
    return ((close - pre_close) / pre_close * Decimal("100")).quantize(
        Decimal("0.000001"),
        rounding=ROUND_HALF_UP,
    )


def _quantize(value: Decimal | None, exponent: str) -> Decimal | None:
    return value.quantize(Decimal(exponent), rounding=ROUND_HALF_UP) if value is not None else None


def _dataframe_rows(data: Any) -> list[dict[str, Any]]:
    if data is None:
        raise AppError(ErrorCode.MARKET_DATA_SOURCE_CHANGED, "AKShare Sina returned an empty response", status_code=502)
    empty = getattr(data, "empty", False)
    if empty:
        return []
    candidate = data
    reset_index = getattr(data, "reset_index", None)
    if callable(reset_index):
        candidate = reset_index()
    to_dict = getattr(candidate, "to_dict", None)
    if not callable(to_dict):
        raise AppError(ErrorCode.MARKET_DATA_SOURCE_CHANGED, "AKShare Sina response is not a DataFrame", status_code=502)
    rows = to_dict("records")
    if not isinstance(rows, list):
        raise AppError(ErrorCode.MARKET_DATA_SOURCE_CHANGED, "AKShare Sina DataFrame rows are not a list", status_code=502)
    return [row for row in rows if isinstance(row, dict)]


def _calendar_days(open_dates: Iterable[date], *, source_code: str) -> list[TradeCalendarDay]:
    previous: date | None = None
    rows: list[TradeCalendarDay] = []
    for trade_date in open_dates:
        rows.append(TradeCalendarDay(trade_date=trade_date, is_open=True, previous_open_date=previous, source_code=source_code))
        previous = trade_date
    return rows


def _sanitized_app_error_type(exc: AppError) -> str:
    if exc.code == ErrorCode.MARKET_DATA_SOURCE_CHANGED:
        return "SourceChanged"
    if exc.code == ErrorCode.MARKET_DATA_SYNC_FAILED:
        return "ConnectionError"
    return "DataInsufficient"


def _sanitized_network_error_type(exc: Exception) -> str:
    names = _exception_names(exc)
    text = repr(exc)
    if "ProxyError" in names or "ProxyError" in text:
        return "ProxyError"
    if "ConnectTimeout" in names or "ConnectTimeout" in text:
        return "ConnectTimeout"
    if "ReadTimeout" in names or "ReadTimeout" in text or "TimeoutError" in names:
        return "ReadTimeout"
    if "ConnectionError" in names or "ConnectionError" in text or "MaxRetryError" in names:
        return "ConnectionError"
    return "ConnectionError"


def _exception_names(exc: BaseException) -> set[str]:
    names: set[str] = set()
    pending: list[BaseException | None] = [exc]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        names.add(current.__class__.__name__)
        pending.append(current.__cause__)
        pending.append(current.__context__)
    return names


def _available_fields(records: list[DailyMarketSnapshotRecord]) -> list[str]:
    fields = SINA_REQUIRED_FIELDS + ["pre_close", "change", "pct_change", "turnover_rate"]
    return sorted({field for record in records for field in fields if getattr(record, field, None) is not None})


def _missing_fields(records: list[DailyMarketSnapshotRecord]) -> list[str]:
    fields = SINA_REQUIRED_FIELDS + [
        "pre_close",
        "change",
        "pct_change",
        "turnover_rate",
        "total_market_value",
        "circulating_market_value",
        "pe_ttm",
        "pb",
        "volume_ratio",
    ]
    if not records:
        return fields
    return sorted({field for record in records for field in fields if getattr(record, field, None) is None})


def _result_status(
    *,
    records: list[DailyMarketSnapshotRecord],
    errors: list[dict[str, str]],
    requested_count: int,
) -> ProviderStatus:
    if records and len(records) == requested_count and not errors:
        if all(record.data_completeness == "complete" for record in records):
            return ProviderStatus.PASS
        return ProviderStatus.PARTIAL
    if records:
        return ProviderStatus.PARTIAL
    codes = {error.get("code") for error in errors}
    if ErrorCode.MARKET_DATA_SOURCE_CHANGED.value in codes:
        return ProviderStatus.SOURCE_CHANGED
    if ErrorCode.MARKET_DATA_SYNC_FAILED.value in codes:
        return ProviderStatus.NETWORK_ERROR
    return ProviderStatus.DATA_INSUFFICIENT
