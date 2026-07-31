from collections import Counter
from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.time import utc_now
from app.models.market_data import MarketDataSource, MarketDataSyncRun, StockDailySnapshot
from app.models.stock import Stock
from app.models.user import User
from app.models.watchlist import UserWatchlistItem
from app.providers.market_data.models import DailyMarketSnapshotRecord, MarketDataQuery
from app.providers.market_data.registry import (
    get_market_data_provider,
    is_market_data_provider_enabled,
    market_data_provider_catalog,
    normalize_market_data_source_code,
)
from app.providers.statuses import ProviderStatus
from app.schemas.market_data import (
    MarketDataStatusOut,
    MarketDataSyncRunOut,
    StockMarketSnapshotOut,
    WatchlistMarketSnapshotOut,
)
from app.schemas.stock import StockRead
from app.services.audit import add_audit_log

UNIT_NOTES = {
    "price": "人民币元/股",
    "pct_change": "百分数，1.25 表示 1.25%",
    "volume": "股",
    "amount": "人民币元",
    "market_value": "人民币元",
    "trade_date": "Asia/Shanghai 交易日",
}

MARKET_SNAPSHOT_FIELDS = [
    "close",
    "pre_close",
    "change",
    "pct_change",
    "open",
    "high",
    "low",
    "volume",
    "amount",
    "turnover_rate",
    "total_market_value",
    "circulating_market_value",
    "pe_ttm",
    "pb",
]

REAL_MARKET_SOURCE_CODES = {"AKSHARE_EASTMONEY", "AKSHARE_SINA_DAILY", "BAOSTOCK", "TUSHARE_PRO"}


async def get_market_data_status(session: AsyncSession, *, settings: Settings) -> MarketDataStatusOut:
    await ensure_default_market_data_sources(session)
    sources = list(
        (await session.execute(select(MarketDataSource).order_by(MarketDataSource.source_code))).scalars().all()
    )
    latest_snapshot = (
        await session.execute(select(StockDailySnapshot).order_by(StockDailySnapshot.trade_date.desc()).limit(1))
    ).scalar_one_or_none()
    latest_run = (
        await session.execute(select(MarketDataSyncRun).order_by(MarketDataSyncRun.started_at.desc()).limit(1))
    ).scalar_one_or_none()
    data_gaps: list[str] = []
    if latest_snapshot is None:
        data_gaps.append("暂无经授权的真实行情数据。前端不得展示 Mock 价格、分时或 K 线。")
    if any(source.source_code == "TUSHARE_PRO" and not source.production_enabled for source in sources):
        data_gaps.append("Tushare 仍为开发验证来源，尚未确认公开展示授权。")

    return MarketDataStatusOut(
        sources=sources,
        providers=[dict(item) for item in market_data_provider_catalog(settings)],
        latest_trade_date=latest_snapshot.trade_date if latest_snapshot else None,
        latest_source_code=latest_snapshot.source_code if latest_snapshot else None,
        latest_fetched_at=latest_snapshot.fetched_at if latest_snapshot else None,
        latest_sync_status=latest_run.status if latest_run else None,
        latest_sync_run=MarketDataSyncRunOut.model_validate(latest_run) if latest_run else None,
        production_authorization_pending=any(
            source.authorization_status != "commercially_authorized" or not source.production_enabled
            for source in sources
            if source.source_code in REAL_MARKET_SOURCE_CODES
        ),
        user_notice="开发验证来源，尚未确认公开展示授权",
        data_gaps=data_gaps,
    )


async def get_stock_market_snapshot(
    session: AsyncSession,
    *,
    stock_id,
) -> StockMarketSnapshotOut:
    stock = await session.get(Stock, stock_id)
    if stock is None:
        raise AppError(ErrorCode.STOCK_NOT_FOUND, "股票不存在", status_code=404)
    snapshot = await latest_snapshot_for_stock(session, stock_id=stock.id)
    source = await get_source_for_snapshot(session, snapshot)
    latest_trade_date = await latest_trade_date_for_source(session, source_code=snapshot.source_code if snapshot else None)
    status = snapshot_status(snapshot, latest_trade_date=latest_trade_date)
    return StockMarketSnapshotOut(
        stock=StockRead.model_validate(stock),
        snapshot=snapshot,
        status=status,
        latest_completed_trade_date=latest_trade_date,
        source_code=snapshot.source_code if snapshot else None,
        authorization_status=source.authorization_status if source else None,
        production_enabled=bool(source.production_enabled) if source else False,
        data_completeness=snapshot.data_completeness if snapshot else None,
        missing_fields=missing_fields_for_snapshot(snapshot),
        message=snapshot_message(status),
        unit_notes=UNIT_NOTES,
    )


async def get_watchlist_market_snapshots(
    session: AsyncSession,
    *,
    user_id,
) -> list[WatchlistMarketSnapshotOut]:
    items = list(
        (
            await session.execute(
                select(UserWatchlistItem)
                .options(selectinload(UserWatchlistItem.stock))
                .where(UserWatchlistItem.user_id == user_id, UserWatchlistItem.archived_at.is_(None))
                .order_by(UserWatchlistItem.sort_order.asc(), UserWatchlistItem.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    if not items:
        return []
    stock_ids = [item.stock_id for item in items]
    snapshots = await latest_snapshots_for_stocks(session, stock_ids=stock_ids)
    latest_trade_date = await latest_trade_date_for_source(session, source_code=None)
    return [
        WatchlistMarketSnapshotOut(
            watchlist_item_id=item.id,
            stock=StockRead.model_validate(item.stock),
            snapshot=snapshots.get(item.stock_id),
            status=snapshot_status(snapshots.get(item.stock_id), latest_trade_date=latest_trade_date),
            data_completeness=snapshots[item.stock_id].data_completeness if snapshots.get(item.stock_id) else None,
            missing_fields=missing_fields_for_snapshot(snapshots.get(item.stock_id)),
            message=snapshot_message(snapshot_status(snapshots.get(item.stock_id), latest_trade_date=latest_trade_date)),
        )
        for item in items
    ]


async def list_market_data_sync_runs(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> tuple[list[MarketDataSyncRun], int]:
    total = (await session.execute(select(func.count()).select_from(MarketDataSyncRun))).scalar_one()
    rows = list(
        (
            await session.execute(
                select(MarketDataSyncRun)
                .order_by(MarketDataSyncRun.started_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return rows, total


async def start_market_data_sync(
    session: AsyncSession,
    *,
    admin_user: User | None,
    source_code: str,
    sync_mode: str,
    trade_date: date | None,
    lookback_days: int,
    stock_ids: list,
    use_current_watchlist: bool,
    dry_run: bool,
    trigger_type: str,
    settings: Settings,
    request_id: str | None,
    max_symbols: int | None = None,
) -> MarketDataSyncRun:
    normalized_source_code = normalize_market_data_source_code(source_code)
    await ensure_default_market_data_sources(session)
    _ensure_sync_allowed(normalized_source_code, settings)
    provider = get_market_data_provider(normalized_source_code, settings)
    if provider is None:
        raise AppError(ErrorCode.MARKET_DATA_PROVIDER_NOT_FOUND, "行情 Provider 尚未实现", status_code=404)
    if not is_market_data_provider_enabled(normalized_source_code, settings):
        raise AppError(ErrorCode.MARKET_DATA_PROVIDER_DISABLED, "行情 Provider 配置未启用", status_code=403)

    if sync_mode == "optional_backfill" and lookback_days > settings.market_data_backfill_max_days:
        raise AppError(ErrorCode.MARKET_DATA_SYNC_LIMIT_EXCEEDED, "回补天数超过当前限制", status_code=422)

    resolved_trade_date = await resolve_trade_date(
        provider=provider,
        mode=sync_mode,
        requested_trade_date=trade_date,
        lookback_days=lookback_days,
        settings=settings,
    )
    stocks = await selected_stocks(
        session,
        user_id=admin_user.id if admin_user and use_current_watchlist else None,
        stock_ids=stock_ids,
        max_symbols=_effective_max_symbols(settings, max_symbols=max_symbols),
    )
    if not stocks:
        raise AppError(ErrorCode.VALIDATION_ERROR, "没有可同步的已存在股票", status_code=422)

    await _ensure_no_running_sync(session, source_code=normalized_source_code, resolved_trade_date=resolved_trade_date)
    now = utc_now()
    run = MarketDataSyncRun(
        source_code=normalized_source_code,
        trigger_type="dry_run" if dry_run else trigger_type,
        sync_mode=sync_mode,
        status="running",
        requested_trade_date=trade_date,
        resolved_trade_date=resolved_trade_date,
        lookback_days=lookback_days,
        requested_symbol_count=len(stocks),
        received_count=0,
        created_count=0,
        updated_count=0,
        unchanged_count=0,
        failure_count=0,
        metrics={"dry_run": dry_run, "unit_notes": UNIT_NOTES},
        started_at=now,
    )
    session.add(run)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(
            ErrorCode.MARKET_DATA_SYNC_ALREADY_RUNNING,
            "该来源和交易日已有行情同步运行中",
            status_code=409,
        ) from exc
    if admin_user:
        await add_audit_log(
            session,
            actor_user_id=admin_user.id,
            action="market_data_sync.start",
            target_type="market_data_sync_run",
            target_id=run.id,
            result="success",
            request_id=request_id,
            metadata={"source_code": normalized_source_code, "trade_date": resolved_trade_date.isoformat()},
        )
    await session.commit()
    await session.refresh(run)

    query = MarketDataQuery(
        trade_date=resolved_trade_date,
        date_from=resolved_trade_date if sync_mode != "optional_backfill" else resolved_trade_date - timedelta(days=lookback_days - 1),
        date_to=resolved_trade_date,
        symbols=[stock.symbol for stock in stocks],
        max_records=settings.market_data_max_symbols_per_run,
        mode=sync_mode,
        dry_run=dry_run,
    )

    try:
        result = await provider.fetch_daily_snapshots(query)
    except AppError as exc:
        run.status = _status_from_error(exc.code)
        run.error_code = exc.code.value
        run.error_summary = exc.message
        run.failure_count = len(stocks)
        run.completed_at = utc_now()
        await session.commit()
        await session.refresh(run)
        if exc.code == ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED:
            raise
        return run
    except Exception as exc:  # noqa: BLE001
        result = ProviderStatus.NETWORK_ERROR
        run.status = result.value
        run.error_code = ErrorCode.MARKET_DATA_SYNC_FAILED.value
        run.error_summary = exc.__class__.__name__
        run.failure_count = len(stocks)
        run.completed_at = utc_now()
        await session.commit()
        await session.refresh(run)
        return run

    counts = Counter({"created": 0, "updated": 0, "unchanged": 0, "failed": 0})
    if not dry_run and result.status in {ProviderStatus.PASS, ProviderStatus.PARTIAL, ProviderStatus.DATA_INSUFFICIENT}:
        counts.update(await persist_market_data_records(session, stocks=stocks, records=result.records))

    run.status = _run_status(result.status, counts["failed"])
    run.received_count = len(result.records)
    run.created_count = counts["created"]
    run.updated_count = counts["updated"]
    run.unchanged_count = counts["unchanged"]
    run.failure_count = result.failure_count + counts["failed"]
    run.metrics = {
        **result.metrics,
        "dry_run": dry_run,
        "unit_notes": UNIT_NOTES,
        "unknown_symbol_count": counts["failed"],
    }
    if result.errors:
        run.error_code = result.errors[0].get("code")
        run.error_summary = result.errors[0].get("summary")
    run.completed_at = utc_now()
    await update_market_data_source_health(
        session,
        source_code=normalized_source_code,
        status=result.status.value,
    )
    if admin_user:
        await add_audit_log(
            session,
            actor_user_id=admin_user.id,
            action="market_data_sync.finish",
            target_type="market_data_sync_run",
            target_id=run.id,
            result="success" if run.status in {"complete", "partial", "data_insufficient"} else "failure",
            request_id=request_id,
            metadata={"source_code": normalized_source_code, "status": run.status},
        )
    await session.commit()
    await session.refresh(run)
    return run


async def ensure_default_market_data_sources(session: AsyncSession) -> None:
    await _ensure_free_market_data_sources(session)
    existing = (
        await session.execute(select(MarketDataSource).where(MarketDataSource.source_code == "TUSHARE_PRO"))
    ).scalar_one_or_none()
    if existing:
        return
    session.add(
        MarketDataSource(
            source_code="TUSHARE_PRO",
            display_name="Tushare Pro",
            source_type="third_party_data_service",
            authorization_status="unverified",
            usage_scope=["local_development", "internal_testing"],
            production_enabled=False,
            capabilities=["daily_snapshot", "trade_calendar"],
            last_health_status="unknown",
            limitations=["开发验证候选；个人 Token 不等于生产授权。"],
        )
    )
    await session.commit()


async def _ensure_free_market_data_sources(session: AsyncSession) -> None:
    defaults = [
        {
            "source_code": "AKSHARE_EASTMONEY",
            "display_name": "AKShare / Eastmoney A-share Daily",
            "source_type": "third_party_data_service",
            "authorization_status": "unverified",
            "usage_scope": ["local_development", "internal_testing"],
            "production_enabled": False,
            "capabilities": ["daily_snapshot", "trade_calendar"],
            "limitations": [
                "AKShare wraps Eastmoney public web data; not official, realtime, or production-authorized.",
                "Diagnostic and explicit cross-check use only; not the default persistence route.",
            ],
        },
        {
            "source_code": "AKSHARE_SINA_DAILY",
            "display_name": "AKShare / Sina BJ Daily",
            "source_type": "third_party_data_service",
            "authorization_status": "unverified",
            "usage_scope": ["local_development", "internal_testing"],
            "production_enabled": False,
            "capabilities": ["daily_snapshot", "trade_calendar"],
            "limitations": [
                "Explicit BJ low-frequency local trial candidate only.",
                "Not official, realtime, or production-authorized.",
            ],
        },
        {
            "source_code": "BAOSTOCK",
            "display_name": "BaoStock A-share Daily",
            "source_type": "third_party_data_service",
            "authorization_status": "unverified",
            "usage_scope": ["local_development", "internal_testing"],
            "production_enabled": False,
            "capabilities": ["daily_snapshot", "trade_calendar", "cross_check"],
            "limitations": [
                "Explicit SH/SZ five-day local trial route.",
                "BJ coverage is unsupported by this adapter.",
            ],
        },
    ]
    existing = {
        source.source_code: source
        for source in (
            await session.execute(
                select(MarketDataSource).where(
                    MarketDataSource.source_code.in_([item["source_code"] for item in defaults])
                )
            )
        )
        .scalars()
        .all()
    }
    changed = False
    for item in defaults:
        source = existing.get(item["source_code"])
        if source is None:
            session.add(MarketDataSource(last_health_status="unknown", **item))
            changed = True
            continue
        for key, value in item.items():
            if getattr(source, key) != value:
                setattr(source, key, value)
                changed = True
    if changed:
        await session.commit()


async def selected_stocks(
    session: AsyncSession,
    *,
    user_id,
    stock_ids: list,
    max_symbols: int,
) -> list[Stock]:
    if stock_ids:
        rows = list(
            (
                await session.execute(
                    select(Stock)
                    .where(Stock.id.in_(stock_ids), Stock.market == "A_SHARE")
                    .order_by(Stock.symbol.asc())
                    .limit(max_symbols)
                )
            )
            .scalars()
            .all()
        )
        return rows
    if user_id:
        rows = list(
            (
                await session.execute(
                    select(Stock)
                    .join(UserWatchlistItem, UserWatchlistItem.stock_id == Stock.id)
                    .where(
                        UserWatchlistItem.user_id == user_id,
                        UserWatchlistItem.archived_at.is_(None),
                        Stock.market == "A_SHARE",
                    )
                    .order_by(UserWatchlistItem.sort_order.asc(), UserWatchlistItem.created_at.asc())
                    .limit(max_symbols)
                )
            )
            .scalars()
            .all()
        )
        return rows
    return []


async def resolve_trade_date(
    *,
    provider,
    mode: str,
    requested_trade_date: date | None,
    lookback_days: int,
    settings: Settings,
) -> date:
    if mode == "selected_trade_date":
        if requested_trade_date is None:
            raise AppError(ErrorCode.VALIDATION_ERROR, "selected_trade_date 模式必须提供 trade_date", status_code=422)
        return requested_trade_date

    sh_now = utc_now().astimezone(ZoneInfo(settings.app_timezone))
    candidate = requested_trade_date or sh_now.date()
    if mode == "latest_completed_trade_day" and (
        sh_now.date() == candidate
        and (sh_now.hour, sh_now.minute) < (settings.market_data_market_close_hour, settings.market_data_market_close_minute)
    ):
        candidate = candidate - timedelta(days=1)
    date_from = candidate - timedelta(days=max(lookback_days + 10, 15))
    calendar = await provider.trade_calendar(
        MarketDataQuery(
            trade_date=candidate,
            date_from=date_from,
            date_to=candidate,
            symbols=[],
            max_records=0,
            mode=mode,
        )
    )
    open_days = [day.trade_date for day in calendar if day.is_open and day.trade_date <= candidate]
    if not open_days:
        raise AppError(ErrorCode.MARKET_DATA_SYNC_FAILED, "无法解析最近完整交易日", status_code=502)
    return max(open_days)


async def persist_market_data_records(
    session: AsyncSession,
    *,
    stocks: list[Stock],
    records: list[DailyMarketSnapshotRecord],
) -> Counter:
    counts: Counter = Counter({"created": 0, "updated": 0, "unchanged": 0, "failed": 0})
    stock_by_symbol = {stock.symbol: stock for stock in stocks}
    seen_symbols: set[str] = set()
    for record in records:
        stock = stock_by_symbol.get(record.symbol)
        if not stock:
            counts["failed"] += 1
            continue
        seen_symbols.add(record.symbol)
        existing = (
            await session.execute(
                select(StockDailySnapshot).where(
                    StockDailySnapshot.stock_id == stock.id,
                    StockDailySnapshot.trade_date == record.trade_date,
                    StockDailySnapshot.source_code == record.source_code,
                )
            )
        ).scalar_one_or_none()
        if not existing:
            session.add(snapshot_from_record(stock_id=stock.id, record=record))
            counts["created"] += 1
            continue
        before = snapshot_fingerprint(existing)
        apply_record(existing, record)
        counts["updated" if before != snapshot_fingerprint(existing) else "unchanged"] += 1
    counts["failed"] += len(set(stock_by_symbol) - seen_symbols)
    return counts


async def latest_snapshot_for_stock(session: AsyncSession, *, stock_id) -> StockDailySnapshot | None:
    return (
        await session.execute(
            select(StockDailySnapshot)
            .where(StockDailySnapshot.stock_id == stock_id)
            .order_by(StockDailySnapshot.trade_date.desc(), StockDailySnapshot.fetched_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def latest_snapshots_for_stocks(session: AsyncSession, *, stock_ids: list) -> dict[Any, StockDailySnapshot]:
    snapshots: dict[Any, StockDailySnapshot] = {}
    rows = list(
        (
            await session.execute(
                select(StockDailySnapshot)
                .where(StockDailySnapshot.stock_id.in_(stock_ids))
                .order_by(StockDailySnapshot.stock_id.asc(), StockDailySnapshot.trade_date.desc())
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        snapshots.setdefault(row.stock_id, row)
    return snapshots


async def latest_trade_date_for_source(session: AsyncSession, *, source_code: str | None) -> date | None:
    statement = select(func.max(StockDailySnapshot.trade_date)).select_from(StockDailySnapshot)
    if source_code:
        statement = statement.where(StockDailySnapshot.source_code == source_code)
    return (await session.execute(statement)).scalar_one_or_none()


async def get_source_for_snapshot(
    session: AsyncSession,
    snapshot: StockDailySnapshot | None,
) -> MarketDataSource | None:
    if snapshot is None:
        return None
    return (
        await session.execute(
            select(MarketDataSource).where(MarketDataSource.source_code == snapshot.source_code).limit(1)
        )
    ).scalar_one_or_none()


async def update_market_data_source_health(
    session: AsyncSession,
    *,
    source_code: str,
    status: str,
) -> None:
    source = (
        await session.execute(select(MarketDataSource).where(MarketDataSource.source_code == source_code))
    ).scalar_one_or_none()
    if source:
        source.last_health_status = status
        source.last_health_checked_at = utc_now()


async def _ensure_no_running_sync(
    session: AsyncSession,
    *,
    source_code: str,
    resolved_trade_date: date,
) -> None:
    running = (
        await session.execute(
            select(MarketDataSyncRun.id)
            .where(
                MarketDataSyncRun.source_code == source_code,
                MarketDataSyncRun.resolved_trade_date == resolved_trade_date,
                MarketDataSyncRun.status == "running",
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if running:
        raise AppError(ErrorCode.MARKET_DATA_SYNC_ALREADY_RUNNING, "该来源和交易日已有行情同步运行中", status_code=409)


def snapshot_status(
    snapshot: StockDailySnapshot | None,
    *,
    latest_trade_date: date | None,
) -> str:
    if snapshot is None:
        return "unavailable"
    if snapshot.data_completeness in {"partial", "insufficient"}:
        return "partial"
    if latest_trade_date and snapshot.trade_date < latest_trade_date:
        return "source_lag"
    return "available"


def snapshot_message(status: str) -> str:
    messages = {
        "available": "已显示最近可用真实日级行情快照。",
        "stale": "该股票行情快照早于最近完整交易日，请关注数据过期状态。",
        "source_lag": "该数据源最新可用日期早于市场交易日历目标，较市场交易日滞后。",
        "partial": "该股票行情字段部分缺失，页面只展示已获得字段。",
        "unavailable": "暂无经授权的真实行情数据。",
    }
    return messages.get(status, "暂无经授权的真实行情数据。")


def missing_fields_for_snapshot(snapshot: StockDailySnapshot | None) -> list[str]:
    if snapshot is None:
        return MARKET_SNAPSHOT_FIELDS.copy()
    return [field for field in MARKET_SNAPSHOT_FIELDS if getattr(snapshot, field) is None]


def snapshot_from_record(*, stock_id, record: DailyMarketSnapshotRecord) -> StockDailySnapshot:
    return StockDailySnapshot(
        stock_id=stock_id,
        source_code=record.source_code,
        trade_date=record.trade_date,
        open=record.open,
        high=record.high,
        low=record.low,
        close=record.close,
        pre_close=record.pre_close,
        change=record.change,
        pct_change=record.pct_change,
        volume=record.volume,
        amount=record.amount,
        turnover_rate=record.turnover_rate,
        volume_ratio=record.volume_ratio,
        total_market_value=record.total_market_value,
        circulating_market_value=record.circulating_market_value,
        pe_ttm=record.pe_ttm,
        pb=record.pb,
        is_trading=record.is_trading,
        data_completeness=record.data_completeness,
        source_updated_at=record.source_updated_at,
        fetched_at=record.fetched_at,
        raw_metadata_hash=record.raw_metadata_hash,
        limitations=record.limitations,
        source_record_ref=record.source_record_ref,
    )


def apply_record(snapshot: StockDailySnapshot, record: DailyMarketSnapshotRecord) -> None:
    for field in [
        "source_code",
        "trade_date",
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
        "volume_ratio",
        "total_market_value",
        "circulating_market_value",
        "pe_ttm",
        "pb",
        "is_trading",
        "data_completeness",
        "source_updated_at",
        "fetched_at",
        "raw_metadata_hash",
        "limitations",
        "source_record_ref",
    ]:
        setattr(snapshot, field, getattr(record, field))


def snapshot_fingerprint(snapshot: StockDailySnapshot) -> tuple:
    return (
        snapshot.open,
        snapshot.high,
        snapshot.low,
        snapshot.close,
        snapshot.pre_close,
        snapshot.change,
        snapshot.pct_change,
        snapshot.volume,
        snapshot.amount,
        snapshot.turnover_rate,
        snapshot.volume_ratio,
        snapshot.total_market_value,
        snapshot.circulating_market_value,
        snapshot.pe_ttm,
        snapshot.pb,
        snapshot.is_trading,
        snapshot.data_completeness,
        snapshot.raw_metadata_hash,
    )


def _ensure_sync_allowed(source_code: str, settings: Settings) -> None:
    if not settings.market_data_sync_enabled:
        raise AppError(ErrorCode.MARKET_DATA_FEATURE_DISABLED, "行情同步功能未启用", status_code=403)
    if source_code in REAL_MARKET_SOURCE_CODES and not settings.market_data_provider_enabled:
        raise AppError(ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED, "行情 Provider 总开关未启用", status_code=503)
    if source_code in {"AKSHARE_EASTMONEY", "AKSHARE_SINA_DAILY", "BAOSTOCK"} and settings.is_production:
        raise AppError(ErrorCode.MARKET_DATA_PERMISSION_DENIED, "免费开发行情源禁止在生产环境启用", status_code=403)
    if source_code == "TUSHARE_PRO" and settings.is_production:
        if settings.market_data_tushare_authorization_status != "commercially_authorized":
            raise AppError(ErrorCode.MARKET_DATA_PERMISSION_DENIED, "Tushare 尚未确认生产授权", status_code=403)
    if source_code == "TUSHARE_PRO" and not settings.market_data_tushare_token.strip():
        raise AppError(ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED, "Tushare Token 未配置", status_code=503)
    if source_code != "MOCK_MARKET_DATA" and not settings.market_data_real_network_enabled:
        raise AppError(ErrorCode.MARKET_DATA_REAL_NETWORK_DISABLED, "行情真实网络同步未启用", status_code=403)


def _effective_max_symbols(settings: Settings, *, max_symbols: int | None) -> int:
    if max_symbols is None:
        return settings.market_data_max_symbols_per_run
    return max(1, min(max_symbols, settings.market_data_max_symbols_per_run))


def _status_from_error(code: ErrorCode) -> str:
    mapping = {
        ErrorCode.MARKET_DATA_PERMISSION_DENIED: ProviderStatus.ACCESS_DENIED.value,
        ErrorCode.MARKET_DATA_PROVIDER_NOT_CONFIGURED: ProviderStatus.DISABLED.value,
        ErrorCode.MARKET_DATA_REAL_NETWORK_DISABLED: ProviderStatus.DISABLED.value,
        ErrorCode.MARKET_DATA_SOURCE_CHANGED: ProviderStatus.SOURCE_CHANGED.value,
    }
    return mapping.get(code, ProviderStatus.NETWORK_ERROR.value)


def _run_status(provider_status: ProviderStatus, failed_count: int) -> str:
    if provider_status == ProviderStatus.PASS and failed_count == 0:
        return "complete"
    if provider_status in {ProviderStatus.PASS, ProviderStatus.PARTIAL}:
        return "partial"
    if provider_status == ProviderStatus.DATA_INSUFFICIENT:
        return "data_insufficient"
    return provider_status.value
