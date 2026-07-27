from collections import Counter
from dataclasses import replace

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.time import utc_now
from app.models.security_master import SecurityMasterSyncRun, SecuritySourceRecord
from app.models.stock import Stock
from app.models.user import User
from app.providers.securities.models import (
    SecurityMasterQuery,
    SecurityMasterRecord,
    SecurityMasterResult,
)
from app.providers.securities.normalization import (
    SEARCHABLE_LISTING_STATUSES,
    SUPPORTED_SECURITY_TYPES,
)
from app.providers.securities.registry import (
    get_security_master_provider,
    is_security_master_provider_enabled,
    normalize_security_master_source_code,
    security_master_provider_catalog,
)
from app.providers.statuses import ProviderStatus
from app.schemas.security_master import (
    SecurityMasterProviderOut,
    SecurityMasterStatusOut,
    SecurityMasterSyncRunOut,
)
from app.services.audit import add_audit_log

SECURITY_MASTER_SOURCE_LIMITATIONS = {
    "SSE_SECURITY_MASTER": ["上交所官方公开目录候选，仍需授权、稳定性和字段口径验证。"],
    "SZSE_SECURITY_MASTER": ["深交所体系公开目录候选；若接口不可稳定访问，需记录 DATA_INSUFFICIENT。"],
    "BSE_SECURITY_MASTER": ["北交所官方公开目录候选；若页面无结构化目录，需记录 DATA_INSUFFICIENT。"],
    "BAOSTOCK_SECURITY_MASTER": ["非官方来源，只能作为开发补充或交叉核验。"],
}

SECURITY_MASTER_SOURCE_LIMITATIONS["BAOSTOCK_DEVELOPMENT_FALLBACK"] = [
    "Non-official development fallback only; disabled by default and blocked outside development."
]

SOURCE_PRIORITIES = {
    "development_seed": 0,
    "BAOSTOCK_SECURITY_MASTER": 50,
    "BAOSTOCK_DEVELOPMENT_FALLBACK": 50,
    "SSE_SECURITY_MASTER": 100,
    "SZSE_SECURITY_MASTER": 100,
    "BSE_SECURITY_MASTER": 100,
}

COMPLETENESS_RULES = {
    "SSE_SECURITY_MASTER": {
        "min_board_counts": {"main_board": 100, "star_board": 50},
        "probe_symbols": {"600519.SH", "688981.SH"},
    },
    "SZSE_SECURITY_MASTER": {
        "min_board_counts": {"main_board": 100, "chinext": 50},
        "probe_symbols": {"000001.SZ", "300750.SZ"},
    },
    "BSE_SECURITY_MASTER": {
        "min_exchange_counts": {"BJ": 1},
        "requires_920_code": True,
    },
    "BAOSTOCK_DEVELOPMENT_FALLBACK": {
        "min_board_counts": {"main_board": 100, "chinext": 50},
        "probe_symbols": {"000001.SZ", "300750.SZ"},
    },
}


def list_security_master_providers(settings: Settings) -> list[SecurityMasterProviderOut]:
    return [SecurityMasterProviderOut(**item) for item in security_master_provider_catalog(settings)]


async def start_security_master_sync(
    session: AsyncSession,
    *,
    admin_user: User,
    source_code: str,
    exchanges: list[str],
    force: bool,
    settings: Settings,
    request_id: str | None,
) -> SecurityMasterSyncRun:
    del force
    normalized_source_code = normalize_security_master_source_code(source_code)
    _ensure_sync_allowed(normalized_source_code, settings)
    provider = get_security_master_provider(normalized_source_code, settings)
    if provider is None:
        raise AppError(ErrorCode.SECURITY_MASTER_PROVIDER_NOT_FOUND, "证券目录 Provider 尚未实现", status_code=404)
    if not is_security_master_provider_enabled(normalized_source_code, settings):
        raise AppError(ErrorCode.SECURITY_MASTER_PROVIDER_DISABLED, "证券目录 Provider 配置未启用", status_code=403)
    await _ensure_no_running_sync(session, source_code=normalized_source_code)

    now = utc_now()
    run = SecurityMasterSyncRun(
        triggered_by_user_id=admin_user.id,
        source_code=normalized_source_code,
        status="running",
        exchanges=_normalize_exchanges(exchanges),
        request_count=0,
        received_count=0,
        created_count=0,
        updated_count=0,
        unchanged_count=0,
        deactivated_count=0,
        failure_count=0,
        started_at=now,
        metrics={"source_limitations": SECURITY_MASTER_SOURCE_LIMITATIONS.get(normalized_source_code, [])},
    )
    session.add(run)
    await add_audit_log(
        session,
        actor_user_id=admin_user.id,
        action="security_master_sync.start",
        target_type="security_master_sync_run",
        target_id=run.id,
        result="success",
        request_id=request_id,
        metadata={"source_code": normalized_source_code, "exchanges": run.exchanges},
    )
    await session.commit()
    await session.refresh(run)

    query = SecurityMasterQuery(
        exchanges=run.exchanges,
        security_types=["common_stock"],
        listing_statuses=["active", "suspended", "risk_warning", "delisting_period", "delisted", "unknown"],
        max_records=settings.security_master_max_records_per_run,
    )
    try:
        result = _apply_completeness_gate(normalized_source_code, await provider.list_securities(query))
    except Exception as exc:  # noqa: BLE001
        result = SecurityMasterResult(
            status=ProviderStatus.NETWORK_ERROR,
            errors=[{"code": ErrorCode.SECURITY_MASTER_SYNC_FAILED.value, "summary": exc.__class__.__name__}],
            metrics={"source_code": normalized_source_code},
            request_count=1,
            failure_count=1,
        )

    counts = await _persist_result(session, source_code=normalized_source_code, result=result)
    run.status = _run_status_from_provider(result.status)
    run.request_count = result.request_count
    run.received_count = len(result.records)
    run.created_count = counts["created"]
    run.updated_count = counts["updated"]
    run.unchanged_count = counts["unchanged"]
    run.deactivated_count = 0
    run.failure_count = result.failure_count + counts["failed"]
    run.completed_at = utc_now()
    run.metrics = {
        **result.metrics,
        "merge_conflict_count": counts["conflicts"],
        "merge_conflict_samples": counts["conflict_samples"],
        "provider_metadata": result.provider_metadata,
        "source_limitations": SECURITY_MASTER_SOURCE_LIMITATIONS.get(normalized_source_code, []),
    }
    if result.errors:
        run.error_code = result.errors[0].get("code")
        run.error_summary = result.errors[0].get("summary")
    await add_audit_log(
        session,
        actor_user_id=admin_user.id,
        action="security_master_sync.finish",
        target_type="security_master_sync_run",
        target_id=run.id,
        result="success" if run.status in {"complete", "partial", "data_insufficient"} else "failure",
        request_id=request_id,
        metadata={"source_code": normalized_source_code, "status": run.status, "received_count": run.received_count},
    )
    await session.commit()
    await session.refresh(run)
    return run


async def list_security_master_sync_runs(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> tuple[list[SecurityMasterSyncRun], int]:
    statement = select(SecurityMasterSyncRun)
    total = (await session.execute(select(func.count()).select_from(SecurityMasterSyncRun))).scalar_one()
    rows = list(
        (
            await session.execute(
                statement.order_by(SecurityMasterSyncRun.started_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return rows, total


async def get_security_master_status(session: AsyncSession) -> SecurityMasterStatusOut:
    total = (await session.execute(select(func.count()).select_from(Stock))).scalar_one()
    active_count = (
        await session.execute(select(func.count()).select_from(Stock).where(Stock.listing_status == "active"))
    ).scalar_one()
    development_seed_count = (
        await session.execute(select(func.count()).select_from(Stock).where(Stock.source_code == "development_seed"))
    ).scalar_one()
    seed_covered_count = (
        await session.execute(
            select(func.count())
            .select_from(Stock)
            .where(Stock.data_source == "development_seed", Stock.source_code != "development_seed")
        )
    ).scalar_one()
    by_exchange = _count_rows(
        (await session.execute(select(Stock.exchange, func.count()).group_by(Stock.exchange))).all()
    )
    by_board = _count_rows((await session.execute(select(Stock.board, func.count()).group_by(Stock.board))).all())
    latest_run = (
        await session.execute(select(SecurityMasterSyncRun).order_by(SecurityMasterSyncRun.started_at.desc()).limit(1))
    ).scalar_one_or_none()
    last_synced_at = (
        await session.execute(select(func.max(Stock.last_synced_at)).select_from(Stock))
    ).scalar_one_or_none()
    sources = list(
        (
            await session.execute(select(Stock.source_code).where(Stock.source_code.is_not(None)).distinct().order_by(Stock.source_code))
        )
        .scalars()
        .all()
    )
    data_gaps = _data_gaps(
        total=total,
        development_seed_count=development_seed_count,
        sources=sources,
        by_exchange=by_exchange,
    )
    return SecurityMasterStatusOut(
        total_count=total,
        by_exchange=by_exchange,
        by_board=by_board,
        active_count=active_count,
        development_seed_count=development_seed_count,
        seed_covered_count=seed_covered_count,
        last_synced_at=last_synced_at,
        sources=sources,
        data_gaps=data_gaps,
        latest_sync_status=latest_run.status if latest_run else None,
        latest_sync_run=SecurityMasterSyncRunOut.model_validate(latest_run) if latest_run else None,
    )


async def _persist_result(
    session: AsyncSession,
    *,
    source_code: str,
    result: SecurityMasterResult,
) -> dict:
    counts = Counter({"created": 0, "updated": 0, "unchanged": 0, "failed": 0, "conflicts": 0})
    conflict_samples: list[dict[str, str]] = []
    if result.status not in {ProviderStatus.PASS, ProviderStatus.PARTIAL, ProviderStatus.DATA_INSUFFICIENT}:
        return {**counts, "conflict_samples": conflict_samples}
    for record in result.records:
        if not _record_supported(record):
            counts["failed"] += 1
            continue
        stock, action, conflicts = await _upsert_stock(session, record)
        if conflicts:
            counts["conflicts"] += len(conflicts)
            conflict_samples.extend(conflicts[: max(0, 10 - len(conflict_samples))])
        await _upsert_source_record(session, stock=stock, record=record, source_code=source_code)
        counts[action] += 1
    return {**counts, "conflict_samples": conflict_samples}


async def _upsert_stock(session: AsyncSession, record: SecurityMasterRecord) -> tuple[Stock, str, list[dict[str, str]]]:
    existing = await _find_existing_stock(session, record)
    now = utc_now()
    if not existing:
        stock = Stock(
            symbol=record.symbol,
            code=record.code,
            exchange=record.exchange,
            name=record.short_name,
            market=record.market,
            board=record.board,
            security_type=record.security_type,
            short_name=record.short_name,
            full_name=record.full_name,
            english_name=record.english_name,
            listing_status=record.listing_status,
            listed_at=record.listed_at,
            delisted_at=record.delisted_at,
            aliases=_merge_aliases([], _record_aliases(record), "", record.short_name),
            pinyin=record.pinyin,
            pinyin_initials=record.pinyin_initials,
            source_code=record.source_code,
            source_record_id=record.provider_security_id,
            source_updated_at=record.source_updated_at,
            last_synced_at=record.fetched_at,
            data_completeness=record.data_completeness,
            is_searchable=_is_searchable(record),
            list_status=_legacy_list_status(record.listing_status),
            list_date=record.listed_at,
            delist_date=record.delisted_at,
            currency="CNY",
            data_source=record.source_code,
        )
        session.add(stock)
        await session.flush()
        return stock, "created", []

    before = _stock_fingerprint(existing)
    conflicts = _source_conflicts(existing, record)
    existing_priority = _source_priority(existing.source_code)
    incoming_priority = _source_priority(record.source_code)

    if incoming_priority < existing_priority:
        previous_short_name = existing.short_name
        existing.aliases = _merge_aliases(existing.aliases, _record_aliases(record), previous_short_name, existing.short_name)
        existing.full_name = existing.full_name or record.full_name
        existing.english_name = existing.english_name or record.english_name
        existing.listed_at = existing.listed_at or record.listed_at
        existing.delisted_at = existing.delisted_at or record.delisted_at
        existing.pinyin = existing.pinyin or record.pinyin
        existing.pinyin_initials = existing.pinyin_initials or record.pinyin_initials
        if existing.data_completeness in {"partial", "insufficient"} and record.data_completeness == "complete":
            existing.data_completeness = "usable"
        existing.last_synced_at = max(
            value for value in [existing.last_synced_at, record.fetched_at] if value is not None
        )
        existing.updated_at = now
        await session.flush()
        return existing, "updated" if before != _stock_fingerprint(existing) else "unchanged", conflicts

    previous_short_name = existing.short_name
    existing.symbol = record.symbol
    existing.code = record.code
    existing.exchange = record.exchange
    existing.name = record.short_name
    existing.market = record.market
    existing.board = record.board
    existing.security_type = record.security_type
    existing.short_name = record.short_name
    existing.full_name = record.full_name
    existing.english_name = record.english_name
    existing.listing_status = record.listing_status
    existing.listed_at = record.listed_at
    existing.delisted_at = record.delisted_at
    existing.aliases = _merge_aliases(existing.aliases, _record_aliases(record), previous_short_name, record.short_name)
    existing.pinyin = record.pinyin or existing.pinyin
    existing.pinyin_initials = record.pinyin_initials or existing.pinyin_initials
    existing.source_code = record.source_code
    existing.source_record_id = record.provider_security_id
    existing.source_updated_at = record.source_updated_at
    existing.last_synced_at = record.fetched_at
    existing.data_completeness = record.data_completeness
    existing.is_searchable = _is_searchable(record)
    existing.list_status = _legacy_list_status(record.listing_status)
    existing.list_date = record.listed_at
    existing.delist_date = record.delisted_at
    if existing.data_source != "development_seed":
        existing.data_source = record.source_code
    existing.updated_at = now
    await session.flush()
    return existing, "updated" if before != _stock_fingerprint(existing) else "unchanged", conflicts


async def _find_existing_stock(session: AsyncSession, record: SecurityMasterRecord) -> Stock | None:
    symbols = {record.symbol}
    codes = {record.code}
    for value in record.previous_symbols:
        normalized = value.strip().upper()
        if not normalized:
            continue
        if "." in normalized:
            symbols.add(normalized)
            codes.add(normalized.split(".", 1)[0])
        else:
            codes.add(normalized)
            symbols.add(f"{normalized}.{record.exchange}")

    return (
        await session.execute(
            select(Stock)
            .where(
                or_(
                    Stock.symbol.in_(symbols),
                    (Stock.exchange == record.exchange) & (Stock.code.in_(codes)),
                )
            )
            .order_by(Stock.created_at.asc(), Stock.id.asc())
            .limit(1)
        )
    ).scalar_one_or_none()


def _source_priority(source_code: str | None) -> int:
    return SOURCE_PRIORITIES.get(source_code or "", 10)


def _record_aliases(record: SecurityMasterRecord) -> list[str]:
    aliases = set(record.aliases)
    aliases.add(record.code)
    aliases.add(record.symbol)
    aliases.update(value.strip().upper() for value in record.previous_symbols if value.strip())
    return sorted(value for value in aliases if value)


def _source_conflicts(existing: Stock, record: SecurityMasterRecord) -> list[dict[str, str]]:
    if _source_priority(record.source_code) >= _source_priority(existing.source_code):
        return []
    conflicts: list[dict[str, str]] = []
    for field, incoming in [
        ("short_name", record.short_name),
        ("board", record.board),
        ("listing_status", record.listing_status),
    ]:
        current = getattr(existing, field)
        if current and incoming and current != incoming:
            conflicts.append(
                {
                    "symbol": existing.symbol,
                    "field": field,
                    "kept_source": existing.source_code,
                    "incoming_source": record.source_code,
                }
            )
    return conflicts


async def _upsert_source_record(
    session: AsyncSession,
    *,
    stock: Stock,
    record: SecurityMasterRecord,
    source_code: str,
) -> None:
    now = utc_now()
    row = (
        await session.execute(
            select(SecuritySourceRecord).where(
                SecuritySourceRecord.source_code == source_code,
                SecuritySourceRecord.provider_security_id == record.provider_security_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        row = SecuritySourceRecord(
            stock_id=stock.id,
            source_code=source_code,
            provider_security_id=record.provider_security_id,
            source_symbol=record.symbol,
            source_name=record.short_name,
            raw_metadata_hash=record.raw_metadata_hash,
            first_seen_at=now,
            last_seen_at=now,
            source_status=record.listing_status,
        )
        session.add(row)
        return
    row.stock_id = stock.id
    row.source_symbol = record.symbol
    row.source_name = record.short_name
    row.raw_metadata_hash = record.raw_metadata_hash
    row.last_seen_at = now
    row.source_status = record.listing_status


def _ensure_sync_allowed(source_code: str, settings: Settings) -> None:
    if not settings.security_master_sync_enabled:
        raise AppError(ErrorCode.SECURITY_MASTER_FEATURE_DISABLED, "证券目录同步功能未启用", status_code=403)
    if settings.is_production:
        raise AppError(ErrorCode.SECURITY_MASTER_REAL_NETWORK_DISABLED, "生产环境默认禁止真实证券目录同步", status_code=403)
    if source_code == "BAOSTOCK_DEVELOPMENT_FALLBACK" and settings.app_env.lower() != "development":
        raise AppError(
            ErrorCode.SECURITY_MASTER_REAL_NETWORK_DISABLED,
            "BaoStock development fallback is only allowed in development",
            status_code=403,
        )
    if not settings.security_master_real_network_enabled:
        raise AppError(ErrorCode.SECURITY_MASTER_REAL_NETWORK_DISABLED, "证券目录真实网络同步未启用", status_code=403)
    if source_code not in SECURITY_MASTER_SOURCE_LIMITATIONS:
        raise AppError(ErrorCode.SECURITY_MASTER_PROVIDER_NOT_FOUND, "证券目录 Provider 尚未实现", status_code=404)


async def _ensure_no_running_sync(session: AsyncSession, *, source_code: str) -> None:
    running = (
        await session.execute(
            select(SecurityMasterSyncRun.id)
            .where(SecurityMasterSyncRun.source_code == source_code, SecurityMasterSyncRun.status == "running")
            .limit(1)
        )
    ).scalar_one_or_none()
    if running:
        raise AppError(ErrorCode.SECURITY_MASTER_SYNC_ALREADY_RUNNING, "该证券目录来源已有同步运行中", status_code=409)


def _normalize_exchanges(exchanges: list[str]) -> list[str]:
    values = [value.strip().upper() for value in exchanges if value.strip()]
    return list(dict.fromkeys(values))


def _record_supported(record: SecurityMasterRecord) -> bool:
    return record.security_type in SUPPORTED_SECURITY_TYPES and record.exchange in {"SH", "SZ", "BJ"} and bool(record.short_name)


def _is_searchable(record: SecurityMasterRecord) -> bool:
    return record.security_type == "common_stock" and record.listing_status in SEARCHABLE_LISTING_STATUSES


def _legacy_list_status(listing_status: str) -> str:
    if listing_status == "delisted":
        return "delisted"
    if listing_status in {"active", "suspended", "risk_warning", "delisting_period"}:
        return "listed"
    return "unknown"


def _run_status_from_provider(status: ProviderStatus) -> str:
    if status == ProviderStatus.PASS:
        return "complete"
    if status == ProviderStatus.PARTIAL:
        return "partial"
    if status == ProviderStatus.DATA_INSUFFICIENT:
        return "data_insufficient"
    return status.value


def _apply_completeness_gate(source_code: str, result: SecurityMasterResult) -> SecurityMasterResult:
    if result.status not in {ProviderStatus.PASS, ProviderStatus.PARTIAL, ProviderStatus.DATA_INSUFFICIENT}:
        return result
    rule = COMPLETENESS_RULES.get(source_code)
    if not rule:
        return result

    board_counts = Counter(record.board for record in result.records)
    exchange_counts = Counter(record.exchange for record in result.records)
    symbols = {record.symbol for record in result.records}
    missing: list[str] = []

    for board, threshold in rule.get("min_board_counts", {}).items():
        if board_counts[board] < threshold:
            missing.append(f"{board}_below_development_threshold")
    for exchange, threshold in rule.get("min_exchange_counts", {}).items():
        if exchange_counts[exchange] < threshold:
            missing.append(f"{exchange}_below_development_threshold")
    for symbol in rule.get("probe_symbols", set()):
        if symbol not in symbols:
            missing.append(f"probe_missing:{symbol}")
    if rule.get("requires_920_code") and not any(record.exchange == "BJ" and record.code.startswith("920") for record in result.records):
        missing.append("bse_current_920_code_missing")

    gate = {
        "passed": not missing,
        "missing": missing,
        "board_counts": dict(board_counts),
        "exchange_counts": dict(exchange_counts),
        "record_count": len(result.records),
    }
    metrics = {**result.metrics, "completeness_gate": gate}
    if missing and result.status == ProviderStatus.PASS:
        return replace(
            result,
            status=ProviderStatus.DATA_INSUFFICIENT,
            errors=[
                *result.errors,
                {
                    "code": "COMPLETENESS_GATE_FAILED",
                    "summary": "Security master source did not satisfy development completeness gate",
                },
            ],
            metrics=metrics,
        )
    return replace(result, metrics=metrics)


def _merge_aliases(existing: list[str] | None, incoming: list[str], previous_name: str, next_name: str) -> list[str]:
    aliases = set(existing or [])
    aliases.update(incoming)
    if previous_name and previous_name != next_name:
        aliases.add(previous_name)
    aliases.add(next_name)
    return sorted(alias for alias in aliases if alias)


def _stock_fingerprint(stock: Stock) -> tuple:
    return (
        stock.symbol,
        stock.code,
        stock.exchange,
        stock.name,
        stock.board,
        stock.security_type,
        stock.short_name,
        stock.full_name,
        stock.english_name,
        stock.listing_status,
        stock.listed_at,
        stock.delisted_at,
        tuple(stock.aliases or []),
        stock.pinyin,
        stock.pinyin_initials,
        stock.source_code,
        stock.source_record_id,
        stock.data_completeness,
        stock.is_searchable,
    )


def _count_rows(rows) -> dict[str, int]:
    return {str(key or "unknown"): int(value) for key, value in rows}


def _data_gaps(
    *,
    total: int,
    development_seed_count: int,
    sources: list[str],
    by_exchange: dict[str, int],
) -> list[str]:
    gaps: list[str] = []
    if total <= 4 and development_seed_count == total:
        gaps.append("当前证券目录仍为开发样本，请管理员先同步真实 A 股证券目录。")
    if "SH" not in by_exchange:
        gaps.append("上交所股票目录尚未覆盖。")
    if "SZ" not in by_exchange:
        gaps.append("深交所股票目录尚未覆盖。")
    if "BJ" not in by_exchange:
        gaps.append("北交所股票目录尚未覆盖。")
    if not any(source != "development_seed" for source in sources):
        gaps.append("尚无真实来源覆盖 development_seed。")
    return gaps
