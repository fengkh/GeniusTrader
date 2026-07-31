import argparse
import asyncio
import json
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Any

from sqlalchemy import select

from app.cli._helpers import first_admin_user
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.errors import AppError, ErrorCode
from app.core.time import utc_now
from app.models.market_data import MarketDataSyncRun, StockDailySnapshot
from app.models.stock import Stock
from app.providers.market_data.models import DailyMarketSnapshotRecord, MarketDataQuery
from app.providers.market_data.registry import (
    get_market_data_provider,
    is_market_data_provider_enabled,
    normalize_market_data_source_code,
)
from app.providers.statuses import ProviderStatus
from app.services.market_data import (
    UNIT_NOTES,
    ensure_default_market_data_sources,
    persist_market_data_records,
    resolve_trade_date,
    snapshot_fingerprint,
    update_market_data_source_health,
)

AUTHORIZATION_NOTE = (
    "Technical reachability is not production authorization; free providers remain unverified, "
    "non-official, local-development/internal-testing only."
)
QUOTE_FIELDS = [
    "open",
    "high",
    "low",
    "close",
    "pre_close",
    "change",
    "pct_change",
    "volume",
    "amount",
    "turnover_rate",
    "total_market_value",
    "circulating_market_value",
    "pe_ttm",
    "pb",
]


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    provider_code = normalize_market_data_source_code(
        args.provider or settings.market_data_default_provider or "BAOSTOCK"
    )
    symbols = _symbols(args.symbols)[: args.max_records]
    if provider_code == "TUSHARE_PRO" and not settings.market_data_tushare_token.strip():
        _print(
            {
                "status": "not_configured",
                "source_status": "blocked_by_local_credential",
                "provider_code": provider_code,
                "error_code": ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED.value,
                "token": "not_configured",
                "authorization_note": AUTHORIZATION_NOTE,
            }
        )
        return 3
    if args.persist and settings.is_production:
        _print(
            {
                "status": "blocked",
                "source_status": "access_denied",
                "provider_code": provider_code,
                "error_code": ErrorCode.MARKET_DATA_PERMISSION_DENIED.value,
                "authorization_note": AUTHORIZATION_NOTE,
            }
        )
        return 1

    provider = get_market_data_provider(provider_code, settings)
    if provider is None:
        _print({"status": "failed", "provider_code": provider_code, "error_code": "PROVIDER_NOT_IMPLEMENTED"})
        return 1
    if not is_market_data_provider_enabled(provider_code, settings):
        _print(
            {
                "status": "not_configured",
                "source_status": "provider_not_configured",
                "provider_code": provider_code,
                "error_code": ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED.value,
                "authorization_note": AUTHORIZATION_NOTE,
            }
        )
        return 3

    stocks_by_symbol = await _resolve_existing_stocks(symbols)
    if args.persist:
        return await _run_fetch_pipeline(
            args=args,
            provider_code=provider_code,
            provider=provider,
            symbols=[symbol for symbol in symbols if symbol in stocks_by_symbol],
            requested_symbols=symbols,
            stocks_by_symbol=stocks_by_symbol,
            persist=True,
        )

    return await _run_fetch_pipeline(
        args=args,
        provider_code=provider_code,
        provider=provider,
        symbols=symbols,
        requested_symbols=symbols,
        stocks_by_symbol=stocks_by_symbol,
        persist=False,
    )


async def _run_fetch_pipeline(
    *,
    args: argparse.Namespace,
    provider_code: str,
    provider,
    symbols: list[str],
    requested_symbols: list[str],
    stocks_by_symbol: dict[str, Stock],
    persist: bool,
) -> int:
    settings = get_settings()
    stage_events: list[dict[str, Any]] = [
        _stage_event("configuration_loaded", provider_code=provider_code),
        _stage_event("provider_initialized", provider_code=provider_code),
    ]
    if persist and not symbols:
        _print(
            {
                "status": "failed",
                "source_status": "data_insufficient",
                "provider_code": provider_code,
                "error_code": "NO_EXISTING_STOCKS",
                "missing_existing_stocks": sorted(set(requested_symbols) - set(stocks_by_symbol)),
                "stage_events": stage_events,
            }
        )
        return 1
    try:
        requested_date = date.fromisoformat(args.date) if args.date else None
        mode = "selected_trade_date" if requested_date and not getattr(args, "latest_completed", False) else "latest_completed_trade_day"
        stage_events.append(_stage_event("calendar_resolution_started", provider_code=provider_code))
        trade_date = await resolve_trade_date(
            provider=provider,
            mode=mode,
            requested_trade_date=requested_date,
            lookback_days=1,
            settings=settings,
        )
        stage_events.append(
            _stage_event("calendar_resolved", provider_code=provider_code, trade_date=trade_date)
        )
        started = perf_counter()
        result = await provider.fetch_daily_snapshots(
            MarketDataQuery(
                trade_date=trade_date,
                date_from=_provider_date_from(provider_code=provider_code, trade_date=trade_date),
                date_to=trade_date,
                symbols=symbols,
                max_records=args.max_records,
                mode=mode,
                dry_run=True,
            )
        )
        elapsed_ms = int((perf_counter() - started) * 1000)
        stage_events.extend(_safe_stage_events(result.metrics.get("stage_events")))
        if persist:
            return await _persist_prefetched_result(
                args=args,
                provider_code=provider_code,
                trade_date=trade_date,
                mode=mode,
                result=result,
                elapsed_ms=elapsed_ms,
                stocks_by_symbol=stocks_by_symbol,
                requested_symbols=requested_symbols,
                stage_events=stage_events,
            )
        cross_check = await _cross_check(
            provider_code=getattr(args, "cross_check_provider", None),
            symbols=symbols,
            trade_date=trade_date,
            max_records=args.max_records,
        )
    except AppError as exc:
        stage_events.append(
            _stage_event(
                "calendar_resolution_failed",
                provider_code=provider_code,
                sanitized_error_code=exc.code.value,
                sanitized_error_type=_sanitized_app_error_type(exc),
            )
        )
        _print(
            {
                "status": "failed",
                "source_status": _source_status_from_error(exc),
                "provider_code": provider_code,
                "error_code": exc.code.value,
                "message": exc.message,
                "token": "configured" if provider_code == "TUSHARE_PRO" else "not_required",
                "authorization_note": AUTHORIZATION_NOTE,
                "stage_events": stage_events,
            }
        )
        return 3 if exc.code == ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED else 1
    except Exception as exc:  # noqa: BLE001
        stage_events.append(
            _stage_event(
                "calendar_resolution_failed",
                provider_code=provider_code,
                sanitized_error_code=ErrorCode.MARKET_DATA_SYNC_FAILED.value,
                sanitized_error_type=_sanitized_exception_type(exc),
            )
        )
        _print(
            {
                "status": "failed",
                "provider_code": provider_code,
                "source_status": "network_error",
                "error_type": _sanitized_exception_type(exc),
                "stage_events": stage_events,
            }
        )
        return 1

    _print(
        {
            "provider_code": provider_code,
            "source_status": result.status.value,
            "dry_run": True,
            "persist": False,
            "trade_date": trade_date.isoformat(),
            "date_resolution_method": mode,
            "request_count": result.request_count,
            "duration_ms": elapsed_ms,
            "record_count": len(result.records),
            "symbols": [
                _record_summary(
                    record,
                    stocks_by_symbol=stocks_by_symbol,
                    attempt_counts=result.metrics.get("attempt_counts", {}),
                )
                for record in sorted(result.records, key=lambda item: item.symbol)
            ],
            "failed_symbols": _failed_symbol_summaries(
                result=result,
                requested_symbols=symbols,
                trade_date=trade_date,
            ),
            "missing_existing_stocks": sorted(set(symbols) - set(stocks_by_symbol)),
            "available_fields": result.metrics.get("available_fields") or _available_fields(result.records),
            "missing_fields": result.metrics.get("missing_fields") or _missing_fields(result.records),
            "raw_units": result.metrics.get("raw_units", {}),
            "normalized_units": result.metrics.get("normalized_units", UNIT_NOTES),
            "data_completeness": _overall_completeness(result.records),
            "warnings": _warnings(result, stocks_by_symbol=stocks_by_symbol, requested_symbols=symbols),
            "limitations": _limitations(result),
            "cross_check": cross_check,
            "stage_events": stage_events,
            "authorization_note": AUTHORIZATION_NOTE,
        }
    )
    return 0 if result.records else 1


async def _persist_prefetched_result(
    *,
    args: argparse.Namespace,
    provider_code: str,
    trade_date: date,
    mode: str,
    result,
    elapsed_ms: int,
    stocks_by_symbol: dict[str, Stock],
    requested_symbols: list[str],
    stage_events: list[dict[str, Any]],
) -> int:
    admin = await first_admin_user()
    if admin is None:
        _print({"status": "failed", "provider_code": provider_code, "error_code": "ADMIN_USER_REQUIRED"})
        return 2
    try:
        async with AsyncSessionLocal() as session:
            stage_events.append(_stage_event("database_transaction_started", provider_code=provider_code))
            await ensure_default_market_data_sources(session)
            stocks = await _reload_stocks(session, stocks_by_symbol=stocks_by_symbol)
            existing_before = await _existing_snapshot_fingerprints(
                session,
                stocks=stocks,
                records=result.records,
            )
            run_row = MarketDataSyncRun(
                source_code=provider_code,
                trigger_type="cli",
                sync_mode=mode,
                status="running",
                requested_trade_date=date.fromisoformat(args.date) if args.date else None,
                resolved_trade_date=trade_date,
                lookback_days=1,
                requested_symbol_count=len(stocks_by_symbol),
                received_count=0,
                created_count=0,
                updated_count=0,
                unchanged_count=0,
                failure_count=0,
                metrics={
                    "dry_run": False,
                    "unit_notes": UNIT_NOTES,
                    "provider_status": result.status.value,
                    "stage_events": stage_events,
                },
                started_at=utc_now(),
            )
            session.add(run_row)
            await session.flush()
            counts = Counter({"created": 0, "updated": 0, "unchanged": 0, "failed": 0})
            snapshot_status_by_symbol = _snapshot_persist_statuses(
                records=result.records,
                stocks_by_symbol=stocks_by_symbol,
                existing_before=existing_before,
            )
            if result.records:
                counts.update(await persist_market_data_records(session, stocks=stocks, records=result.records))
                for event in _snapshot_events(
                    provider_code=provider_code,
                    records=result.records,
                    stocks_by_symbol=stocks_by_symbol,
                ):
                    stage_events.append(event)
            run_row.status = _prefetched_run_status(result.status, counts=counts, record_count=len(result.records))
            run_row.received_count = len(result.records)
            run_row.created_count = counts["created"]
            run_row.updated_count = counts["updated"]
            run_row.unchanged_count = counts["unchanged"]
            run_row.failure_count = max(result.failure_count, counts["failed"])
            run_row.metrics = {
                **result.metrics,
                "dry_run": False,
                "unit_notes": UNIT_NOTES,
                "unknown_symbol_count": counts["failed"],
                "stage_events": stage_events,
            }
            if result.errors:
                run_row.error_code = result.errors[0].get("code")
                run_row.error_summary = result.errors[0].get("summary")
            run_row.completed_at = utc_now()
            await update_market_data_source_health(
                session,
                source_code=provider_code,
                status=result.status.value,
            )
            stage_events.append(_stage_event("database_transaction_committed", provider_code=provider_code))
            stage_events.append(_stage_event("sync_completed", provider_code=provider_code, trade_date=trade_date))
            await session.commit()
            await session.refresh(run_row)
    except AppError as exc:
        _print(
            {
                "status": "failed",
                "source_status": _source_status_from_error(exc),
                "provider_code": provider_code,
                "error_code": exc.code.value,
                "message": exc.message,
                "authorization_note": AUTHORIZATION_NOTE,
                "stage_events": stage_events,
            }
        )
        return 1
    _print(
        {
            "provider_code": provider_code,
            "source_status": run_row.status,
            "dry_run": False,
            "persist": True,
            "job_run_id": str(run_row.id),
            "trade_date": run_row.resolved_trade_date.isoformat() if run_row.resolved_trade_date else None,
            "duration_ms": elapsed_ms,
            "request_count": run_row.requested_symbol_count,
            "received_count": run_row.received_count,
            "created_count": run_row.created_count,
            "updated_count": run_row.updated_count,
            "unchanged_count": run_row.unchanged_count,
            "failure_count": run_row.failure_count,
            "raw_units": run_row.metrics.get("raw_units", {}),
            "normalized_units": run_row.metrics.get("unit_notes", UNIT_NOTES),
            "symbols": _persist_symbol_summaries(
                records=result.records,
                requested_symbols=requested_symbols,
                stocks_by_symbol=stocks_by_symbol,
                attempt_counts=result.metrics.get("attempt_counts", {}),
                trade_date=trade_date,
                created_symbols={
                    symbol for symbol, status in snapshot_status_by_symbol.items() if status == "inserted"
                },
                updated_symbols={
                    symbol for symbol, status in snapshot_status_by_symbol.items() if status == "updated"
                },
            ),
            "failed_symbols": _failed_symbol_summaries(
                result=result,
                requested_symbols=requested_symbols,
                trade_date=trade_date,
            ),
            "missing_existing_stocks": sorted(set(requested_symbols) - set(stocks_by_symbol)),
            "stage_events": stage_events,
            "authorization_note": AUTHORIZATION_NOTE,
        }
    )
    return 0 if run_row.status in {"complete", "partial", "data_insufficient"} else 1


async def _cross_check(
    *,
    provider_code: str | None,
    symbols: list[str],
    trade_date: date,
    max_records: int,
) -> dict[str, Any] | None:
    if not provider_code:
        return None
    settings = get_settings()
    normalized = normalize_market_data_source_code(provider_code)
    provider = get_market_data_provider(normalized, settings)
    if provider is None or not is_market_data_provider_enabled(normalized, settings):
        return {"provider_code": normalized, "source_status": "provider_not_configured"}
    result = await provider.fetch_daily_snapshots(
        MarketDataQuery(
            trade_date=trade_date,
            date_from=trade_date,
            date_to=trade_date,
            symbols=symbols,
            max_records=max_records,
            mode="selected_trade_date",
            dry_run=True,
        )
    )
    by_symbol = {record.symbol: record for record in result.records}
    return {
        "provider_code": normalized,
        "source_status": result.status.value,
        "same_trade_date": all(record.trade_date == trade_date for record in result.records),
        "field_difference_summary": {
            symbol: _cross_record_summary(record)
            for symbol, record in sorted(by_symbol.items())
        },
        "provider_limitations": _limitations(result),
    }


async def _resolve_existing_stocks(symbols: list[str]) -> dict[str, Stock]:
    async with AsyncSessionLocal() as session:
        rows = list(
            (
                await session.execute(
                    select(Stock).where(Stock.symbol.in_(symbols), Stock.market == "A_SHARE")
                )
            )
            .scalars()
            .all()
        )
    return {row.symbol: row for row in rows}


async def _reload_stocks(session, *, stocks_by_symbol: dict[str, Stock]) -> list[Stock]:
    if not stocks_by_symbol:
        return []
    rows = list(
        (
            await session.execute(
                select(Stock)
                .where(Stock.id.in_([stock.id for stock in stocks_by_symbol.values()]))
                .order_by(Stock.symbol.asc())
            )
        )
        .scalars()
        .all()
    )
    return rows


async def _existing_snapshot_fingerprints(
    session,
    *,
    stocks: list[Stock],
    records: list[DailyMarketSnapshotRecord],
) -> dict[tuple[Any, date, str], tuple]:
    if not stocks or not records:
        return {}
    stock_ids = [stock.id for stock in stocks]
    trade_dates = sorted({record.trade_date for record in records})
    source_codes = sorted({record.source_code for record in records})
    snapshots = list(
        (
            await session.execute(
                select(StockDailySnapshot).where(
                    StockDailySnapshot.stock_id.in_(stock_ids),
                    StockDailySnapshot.trade_date.in_(trade_dates),
                    StockDailySnapshot.source_code.in_(source_codes),
                )
            )
        )
        .scalars()
        .all()
    )
    return {
        (snapshot.stock_id, snapshot.trade_date, snapshot.source_code): snapshot_fingerprint(snapshot)
        for snapshot in snapshots
    }


def _record_summary(
    record: DailyMarketSnapshotRecord,
    *,
    stocks_by_symbol: dict[str, Stock],
    attempt_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    stock = stocks_by_symbol.get(record.symbol)
    return {
        "symbol": record.symbol,
        "stock_id": str(stock.id) if stock else None,
        "fetch_status": "succeeded",
        "attempt_count": (attempt_counts or {}).get(record.symbol, 1),
        "normalization_status": "succeeded",
        "exchange": stock.exchange if stock else record.symbol.split(".")[-1],
        "trade_date": record.trade_date.isoformat(),
        "available_fields": [field for field in QUOTE_FIELDS if getattr(record, field) is not None],
        "missing_fields": [field for field in QUOTE_FIELDS if getattr(record, field) is None],
        "raw_units": record_raw_units(record),
        "normalized_units": {"price": "CNY/share", "volume": "share", "amount": "CNY", "pct_change": "percent_number"},
        "data_completeness": record.data_completeness,
        "warnings": [item for item in record.limitations if item.startswith("missing_field:")],
        "limitations": [item for item in record.limitations if not item.startswith("missing_field:")],
    }


def _failed_symbol_summaries(
    *,
    result,
    requested_symbols: list[str],
    trade_date: date,
) -> list[dict[str, Any]]:
    returned_symbols = {record.symbol for record in result.records}
    attempt_counts = result.metrics.get("attempt_counts", {})
    error_type = _sanitized_provider_error_type(result.errors[0]) if result.errors else "DataInsufficient"
    error_code = result.errors[0].get("code") if result.errors else "DATA_INSUFFICIENT"
    return [
        {
            "symbol": symbol,
            "trade_date": trade_date.isoformat(),
            "fetch_status": "failed",
            "attempt_count": attempt_counts.get(symbol, 0),
            "normalization_status": "failed",
            "persist_status": "not_persisted",
            "snapshot_inserted": False,
            "snapshot_updated": False,
            "sanitized_error_code": error_code,
            "sanitized_error_type": error_type,
        }
        for symbol in requested_symbols
        if symbol not in returned_symbols
    ]


def _persist_symbol_summaries(
    *,
    records: list[DailyMarketSnapshotRecord],
    requested_symbols: list[str],
    stocks_by_symbol: dict[str, Stock],
    attempt_counts: dict[str, int] | None,
    trade_date: date,
    created_symbols: set[str],
    updated_symbols: set[str],
) -> list[dict[str, Any]]:
    by_symbol = {record.symbol: record for record in records}
    summaries: list[dict[str, Any]] = []
    for symbol in requested_symbols:
        stock = stocks_by_symbol.get(symbol)
        record = by_symbol.get(symbol)
        if record is None:
            summaries.append(
                {
                    "symbol": symbol,
                    "stock_id": str(stock.id) if stock else None,
                    "trade_date": trade_date.isoformat(),
                    "fetch_status": "failed",
                    "attempt_count": (attempt_counts or {}).get(symbol, 0),
                    "normalization_status": "failed",
                    "persist_status": "not_persisted",
                    "snapshot_inserted": False,
                    "snapshot_updated": False,
                    "sanitized_error_type": "DataInsufficient",
                }
            )
            continue
        summaries.append(
            {
                "symbol": record.symbol,
                "stock_id": str(stock.id) if stock else None,
                "trade_date": record.trade_date.isoformat(),
                "fetch_status": "succeeded",
                "attempt_count": (attempt_counts or {}).get(record.symbol, 1),
                "normalization_status": "succeeded",
                "persist_status": (
                    "inserted"
                    if record.symbol in created_symbols
                    else "updated"
                    if record.symbol in updated_symbols
                    else "unchanged"
                ),
                "snapshot_inserted": record.symbol in created_symbols,
                "snapshot_updated": record.symbol in updated_symbols,
                "sanitized_error_type": None,
            }
        )
    return summaries


def _snapshot_persist_statuses(
    *,
    records: list[DailyMarketSnapshotRecord],
    stocks_by_symbol: dict[str, Stock],
    existing_before: dict[tuple[Any, date, str], tuple],
) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for record in records:
        stock = stocks_by_symbol.get(record.symbol)
        if stock is None:
            statuses[record.symbol] = "failed"
            continue
        key = (stock.id, record.trade_date, record.source_code)
        if key not in existing_before:
            statuses[record.symbol] = "inserted"
        elif existing_before[key] != _record_fingerprint(record):
            statuses[record.symbol] = "updated"
        else:
            statuses[record.symbol] = "unchanged"
    return statuses


def _snapshot_events(
    *,
    provider_code: str,
    records: list[DailyMarketSnapshotRecord],
    stocks_by_symbol: dict[str, Stock],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for record in records:
        stock = stocks_by_symbol.get(record.symbol)
        if stock:
            events.append(
                _stage_event(
                    "snapshot_upserted",
                    provider_code=provider_code,
                    symbol=record.symbol,
                    stock_id=str(stock.id),
                    trade_date=record.trade_date,
                )
            )
    return events


def _record_fingerprint(record: DailyMarketSnapshotRecord) -> tuple:
    return (
        record.open,
        record.high,
        record.low,
        record.close,
        record.pre_close,
        record.change,
        record.pct_change,
        record.volume,
        record.amount,
        record.turnover_rate,
        record.volume_ratio,
        record.total_market_value,
        record.circulating_market_value,
        record.pe_ttm,
        record.pb,
        record.is_trading,
        record.data_completeness,
        record.raw_metadata_hash,
    )


def _cross_record_summary(record: DailyMarketSnapshotRecord) -> dict[str, Any]:
    return {
        "trade_date": record.trade_date.isoformat(),
        "open": _decimal(record.open),
        "high": _decimal(record.high),
        "low": _decimal(record.low),
        "close": _decimal(record.close),
        "volume": _decimal(record.volume),
        "amount": _decimal(record.amount),
        "pct_change": _decimal(record.pct_change),
    }


def record_raw_units(record: DailyMarketSnapshotRecord) -> dict[str, str]:
    if record.source_code == "AKSHARE_EASTMONEY":
        return {"volume": "lot", "amount": "CNY"}
    if record.source_code == "AKSHARE_SINA_DAILY":
        return {"volume": "share", "amount": "CNY", "turnover_rate": "ratio_or_percent_number"}
    if record.source_code == "BAOSTOCK":
        return {"volume": "share", "amount": "CNY"}
    return {"volume": "provider_specific", "amount": "provider_specific"}


def _symbols(raw: str) -> list[str]:
    values = [item.strip().upper() for item in raw.split(",") if item.strip()]
    return values if values else ["600519.SH", "300750.SZ", "688981.SH", "920000.BJ"]


def _provider_date_from(*, provider_code: str, trade_date: date) -> date:
    if provider_code == "AKSHARE_SINA_DAILY":
        return trade_date - timedelta(days=1)
    return trade_date


def _source_status_from_error(exc: AppError) -> str:
    if exc.code == ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED:
        return "provider_not_configured"
    if exc.code == ErrorCode.MARKET_DATA_REAL_NETWORK_DISABLED:
        return ProviderStatus.DISABLED.value
    if exc.code == ErrorCode.MARKET_DATA_SOURCE_CHANGED:
        return ProviderStatus.SOURCE_CHANGED.value
    if exc.code == ErrorCode.MARKET_DATA_PERMISSION_DENIED:
        return ProviderStatus.ACCESS_DENIED.value
    return ProviderStatus.NETWORK_ERROR.value


def _available_fields(records: list[DailyMarketSnapshotRecord]) -> list[str]:
    return sorted({field for record in records for field in QUOTE_FIELDS if getattr(record, field) is not None})


def _missing_fields(records: list[DailyMarketSnapshotRecord]) -> list[str]:
    if not records:
        return QUOTE_FIELDS.copy()
    return sorted({field for record in records for field in QUOTE_FIELDS if getattr(record, field) is None})


def _overall_completeness(records: list[DailyMarketSnapshotRecord]) -> str:
    if not records:
        return "insufficient"
    if all(record.data_completeness == "complete" for record in records):
        return "complete"
    return "partial"


def _warnings(
    result,
    *,
    stocks_by_symbol: dict[str, Stock],
    requested_symbols: list[str],
) -> list[str]:
    warnings = [error.get("code", "") for error in result.errors if error.get("code")]
    warnings.extend(f"missing_stock:{symbol}" for symbol in sorted(set(requested_symbols) - set(stocks_by_symbol)))
    return warnings


def _limitations(result) -> list[str]:
    values: set[str] = set()
    for record in result.records:
        values.update(item for item in record.limitations if not item.startswith("missing_field:"))
    return sorted(values)


def _prefetched_run_status(provider_status: ProviderStatus, *, counts: Counter, record_count: int) -> str:
    if record_count == 0:
        return "failed"
    if provider_status == ProviderStatus.PASS and counts["failed"] == 0:
        return "complete"
    if provider_status in {ProviderStatus.PASS, ProviderStatus.PARTIAL}:
        return "partial"
    if provider_status == ProviderStatus.DATA_INSUFFICIENT:
        return "data_insufficient"
    return "failed"


def _stage_event(
    stage: str,
    *,
    provider_code: str,
    symbol: str | None = None,
    stock_id: str | None = None,
    trade_date: date | None = None,
    attempt: int | None = None,
    duration_ms: int | None = None,
    sanitized_error_code: str | None = None,
    sanitized_error_type: str | None = None,
) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "provider_code": provider_code,
            "symbol": symbol,
            "stock_id": stock_id,
            "trade_date": trade_date.isoformat() if trade_date else None,
            "stage": stage,
            "attempt": attempt,
            "duration_ms": duration_ms,
            "sanitized_error_code": sanitized_error_code,
            "sanitized_error_type": sanitized_error_type,
        }.items()
        if value is not None
    }


def _safe_stage_events(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    allowed = {
        "provider_code",
        "symbol",
        "stock_id",
        "trade_date",
        "stage",
        "attempt",
        "duration_ms",
        "sanitized_error_code",
        "sanitized_error_type",
    }
    events: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            events.append({key: item[key] for key in allowed if key in item})
    return events


def _sanitized_app_error_type(exc: AppError) -> str:
    if exc.code == ErrorCode.MARKET_DATA_SOURCE_CHANGED:
        return "SourceChanged"
    if exc.code in {ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED, ErrorCode.VALIDATION_ERROR}:
        return "DataInsufficient"
    return "ConnectionError"


def _sanitized_provider_error_type(error: dict[str, str]) -> str:
    code = error.get("code", "")
    summary = error.get("summary", "")
    if code == ErrorCode.MARKET_DATA_SOURCE_CHANGED.value:
        return "SourceChanged"
    if code in {"NO_TARGET_TRADE_DATE", "SOURCE_LAG", "BAOSTOCK_BJ_UNVERIFIED", "TRADE_DATE_REQUIRED"}:
        return "DataInsufficient"
    return _sanitized_error_name(summary)


def _sanitized_exception_type(exc: Exception) -> str:
    return _sanitized_error_name(type(exc).__name__)


def _sanitized_error_name(value: str) -> str:
    if "ProxyError" in value:
        return "ProxyError"
    if "ConnectTimeout" in value:
        return "ConnectTimeout"
    if "ReadTimeout" in value or "TimeoutError" in value:
        return "ReadTimeout"
    if "SourceChanged" in value:
        return "SourceChanged"
    if "DataInsufficient" in value:
        return "DataInsufficient"
    return "ConnectionError"


def _decimal(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _print(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)
    token = get_settings().market_data_tushare_token.strip()
    if token:
        text = text.replace(token, "[redacted]")
    print(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test a market data provider without persisting by default")
    parser.add_argument(
        "--provider",
        default=None,
        help="Provider code, e.g. BAOSTOCK, AKSHARE_SINA_DAILY, AKSHARE_EASTMONEY, TUSHARE_PRO",
    )
    parser.add_argument(
        "--symbols",
        default="600519.SH,300750.SZ,688981.SH,920000.BJ",
        help="Comma-separated existing stock symbols; max four by default",
    )
    parser.add_argument("--date", help="Trade date in YYYY-MM-DD; defaults to latest completed trade day")
    parser.add_argument("--latest-completed", action="store_true", help="Force latest completed trade day resolution")
    parser.add_argument("--max-records", type=int, default=4, choices=[1, 2, 3, 4], help="Maximum symbols/records to request")
    parser.add_argument("--dry-run", action="store_true", help="Run as technical smoke; does not write database records")
    parser.add_argument("--persist", action="store_true", help="Persist only explicit existing stock IDs/symbols after validation")
    parser.add_argument("--cross-check-provider", help="Optional explicit cross-check provider, e.g. BAOSTOCK")
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
