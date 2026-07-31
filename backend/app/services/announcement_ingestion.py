import hashlib
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.time import utc_now
from app.core.url_security import stable_hash
from app.models.external_source import (
    AnnouncementRecord,
    ExternalSource,
    InformationIngestionLink,
    ProviderSyncRun,
    ProviderSyncState,
    UserAnnouncementCandidate,
)
from app.models.information import (
    InformationContent,
    InformationItem,
    InformationSource,
    InformationStockRelation,
)
from app.models.stock import Stock
from app.models.watchlist import UserWatchlistItem
from app.providers.announcements.base import AnnouncementQuery
from app.providers.announcements.document_extraction import extract_announcement_pdf
from app.providers.announcements.models import NormalizedAnnouncement
from app.providers.announcements.registry import (
    get_announcement_provider,
    is_provider_enabled,
    provider_catalog,
)
from app.providers.external_sources import FUTURE_SOURCE_GROUPS
from app.providers.statuses import ProviderStatus
from app.schemas.announcement_ingestion import (
    AnnouncementCandidateDetailOut,
    AnnouncementCandidateSummaryOut,
    AnnouncementDocumentExtractOut,
    AnnouncementImportOut,
    ProviderSyncRunOut,
)
from app.schemas.external_sources import AnnouncementProviderOut, FutureSourceGroupOut
from app.services.audit import add_audit_log
from app.services.html_extraction import normalize_whitespace
from app.services.information import content_hash

ANNOUNCEMENT_CAPABILITY = "announcement_list"
MAX_SYNC_DATE_RANGE_DAYS = 31


async def list_external_sources(
    session: AsyncSession,
    *,
    source_category: str | None,
    country_code: str | None,
    authority_level: str | None,
    source_tier: str | None,
    enabled: bool | None,
    experimental: bool | None,
) -> list[ExternalSource]:
    statement = select(ExternalSource).order_by(ExternalSource.source_code)
    if source_category:
        statement = statement.where(ExternalSource.source_category == source_category)
    if country_code:
        statement = statement.where(ExternalSource.country_code == country_code)
    if authority_level:
        statement = statement.where(ExternalSource.authority_level == authority_level)
    if source_tier:
        statement = statement.where(ExternalSource.source_tier == source_tier)
    if enabled is not None:
        statement = statement.where(ExternalSource.enabled.is_(enabled))
    if experimental is not None:
        statement = statement.where(ExternalSource.experimental.is_(experimental))
    return list((await session.execute(statement)).scalars().all())


def list_announcement_providers(settings: Settings) -> list[AnnouncementProviderOut]:
    return [AnnouncementProviderOut(**item) for item in provider_catalog(settings)]


def list_future_source_groups() -> list[FutureSourceGroupOut]:
    return [FutureSourceGroupOut(**item) for item in FUTURE_SOURCE_GROUPS]


async def start_announcement_sync_run(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    source_code: str,
    date_from: date,
    date_to: date,
    stock_ids: list[uuid.UUID],
    use_current_watchlist: bool,
    settings: Settings,
    request_id: str | None,
    dry_run: bool = False,
    max_records: int | None = None,
) -> ProviderSyncRun:
    source = await _get_external_source_or_404(session, source_code=source_code)
    _ensure_sync_allowed(source, settings)
    _validate_date_range(date_from, date_to, settings)
    provider = get_announcement_provider(source.source_code, settings)
    if provider is None:
        raise AppError(ErrorCode.ANNOUNCEMENT_PROVIDER_NOT_FOUND, "公告 Provider 尚未实现", status_code=404)
    if not is_provider_enabled(source.source_code, settings):
        raise AppError(ErrorCode.ANNOUNCEMENT_PROVIDER_DISABLED, "公告 Provider 配置未启用", status_code=403)
    await _ensure_no_running_sync(session, user_id=user_id)
    watchlist = await _selected_watchlist(session, user_id=user_id, stock_ids=stock_ids, use_current_watchlist=use_current_watchlist)
    if len(watchlist) > settings.announcement_max_symbols_per_run:
        raise AppError(ErrorCode.ANNOUNCEMENT_SYNC_LIMIT_EXCEEDED, "本次公告同步股票数量超过限制", status_code=422)
    requested_symbols = [_stock_symbol(stock) for _item, stock in watchlist]
    now = utc_now()
    run = ProviderSyncRun(
        external_source_id=source.id,
        capability=ANNOUNCEMENT_CAPABILITY,
        triggered_by_user_id=user_id,
        status="running",
        date_from=date_from,
        date_to=date_to,
        requested_symbols=requested_symbols,
        request_count=0,
        success_count=0,
        failure_count=0,
        record_count=0,
        candidate_count=0,
        created_record_count=0,
        updated_record_count=0,
        duplicate_record_count=0,
        metrics={},
        provider_metadata={"source_code": source.source_code, "experimental": True},
        started_at=now,
        created_at=now,
    )
    session.add(run)
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="announcement_sync.start",
        target_type="provider_sync_run",
        target_id=run.id,
        result="success",
        request_id=request_id,
        metadata={"source_code": source.source_code, "symbol_count": len(requested_symbols)},
    )
    await session.commit()
    await session.refresh(run)

    if not requested_symbols:
        run.status = "data_insufficient"
        run.completed_at = utc_now()
        run.error_code = "NO_WATCHLIST_SYMBOLS"
        run.error_summary = "当前用户没有可用于公告同步的自选股。"
        await _update_sync_state(session, source=source, user_id=user_id, run=run, next_cursor=None)
        await session.commit()
        await session.refresh(run)
        return run

    query = AnnouncementQuery(
        date_from=date_from,
        date_to=date_to,
        symbols=requested_symbols,
        cursor=None,
        max_records=_effective_max_records(settings, max_records=max_records),
    )
    try:
        result = await provider.list_announcements(query)
    except AppError as exc:
        run.status = "failed"
        run.failure_count = 1
        run.error_code = exc.code.value
        run.error_summary = exc.message
        run.completed_at = utc_now()
        source.health_status = "network_error"
        await _update_sync_state(session, source=source, user_id=user_id, run=run, next_cursor=None)
        await add_audit_log(
            session,
            actor_user_id=user_id,
            action="announcement_sync.finish",
            target_type="provider_sync_run",
            target_id=run.id,
            result="failure",
            request_id=request_id,
            metadata={"source_code": source.source_code, "error_code": exc.code.value},
        )
        await session.commit()
        raise
    except Exception as exc:
        run.status = "failed"
        run.failure_count = 1
        run.error_code = ErrorCode.ANNOUNCEMENT_SYNC_FAILED.value
        run.error_summary = exc.__class__.__name__
        run.completed_at = utc_now()
        source.health_status = "network_error"
        await _update_sync_state(session, source=source, user_id=user_id, run=run, next_cursor=None)
        await add_audit_log(
            session,
            actor_user_id=user_id,
            action="announcement_sync.finish",
            target_type="provider_sync_run",
            target_id=run.id,
            result="failure",
            request_id=request_id,
            metadata={"source_code": source.source_code, "error_code": ErrorCode.ANNOUNCEMENT_SYNC_FAILED.value},
        )
        await session.commit()
        raise AppError(ErrorCode.ANNOUNCEMENT_SYNC_FAILED, "公告同步失败", status_code=502) from exc
    if dry_run:
        counts = {
            "candidate_count": 0,
            "created_record_count": 0,
            "updated_record_count": 0,
            "duplicate_record_count": 0,
        }
    else:
        counts = await _persist_provider_result(
            session,
            user_id=user_id,
            source=source,
            run=run,
            records=result.records,
            watchlist=watchlist,
        )
    run.status = _run_status_from_provider_status(result.status)
    run.request_count = result.request_count
    run.success_count = result.success_count
    run.failure_count = result.failure_count
    run.record_count = len(result.records)
    run.candidate_count = counts["candidate_count"]
    run.created_record_count = counts["created_record_count"]
    run.updated_record_count = counts["updated_record_count"]
    run.duplicate_record_count = counts["duplicate_record_count"]
    run.metrics = {**result.metrics, "dry_run": dry_run}
    run.provider_metadata = result.provider_metadata
    run.completed_at = utc_now()
    if result.errors:
        run.error_code = result.errors[0].get("code")
        run.error_summary = result.errors[0].get("summary")
    source.health_status = result.status.value
    await _update_sync_state(session, source=source, user_id=user_id, run=run, next_cursor=result.next_cursor)
    await session.commit()
    await session.refresh(run)
    return run


async def list_announcement_sync_runs(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[ProviderSyncRun], int]:
    statement = select(ProviderSyncRun).where(ProviderSyncRun.triggered_by_user_id == user_id)
    total = (await session.execute(select(func.count()).select_from(statement.order_by(None).subquery()))).scalar_one()
    runs = list(
        (
            await session.execute(statement.order_by(ProviderSyncRun.started_at.desc()).limit(limit).offset(offset))
        )
        .scalars()
        .all()
    )
    return runs, total


async def get_announcement_sync_run_or_404(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    run_id: uuid.UUID,
) -> ProviderSyncRun:
    run = (
        await session.execute(
            select(ProviderSyncRun).where(
                ProviderSyncRun.id == run_id,
                ProviderSyncRun.triggered_by_user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not run:
        raise AppError(ErrorCode.ANNOUNCEMENT_SYNC_FAILED, "公告同步运行不存在", status_code=404)
    return run


async def list_announcement_candidates(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    status: str | None,
    source_code: str | None,
    stock_id: uuid.UUID | None,
    announcement_type: str | None,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
    limit: int,
    offset: int,
) -> tuple[list[AnnouncementCandidateSummaryOut], int]:
    statement = _candidate_select().where(UserAnnouncementCandidate.user_id == user_id)
    if status:
        statement = statement.where(UserAnnouncementCandidate.status == status)
    else:
        statement = statement.where(UserAnnouncementCandidate.status.in_(["pending", "reviewed"]))
    statement = _apply_candidate_filters(
        statement,
        source_code=source_code,
        stock_id=stock_id,
        announcement_type=announcement_type,
        date_from=date_from,
        date_to=date_to,
        q=q,
    )
    total = (await session.execute(select(func.count()).select_from(statement.order_by(None).subquery()))).scalar_one()
    rows = (
        await session.execute(
            statement.order_by(AnnouncementRecord.published_at.desc().nullslast(), UserAnnouncementCandidate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return [_candidate_summary_out(*row) for row in rows], total


async def get_announcement_candidate_detail(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> AnnouncementCandidateDetailOut:
    candidate, record, source = await _candidate_tuple_or_404(session, user_id=user_id, candidate_id=candidate_id)
    link = await _ingestion_link_for_candidate(session, user_id=user_id, candidate_id=candidate.id)
    summary = _candidate_summary_out(candidate, record, source).model_dump()
    return AnnouncementCandidateDetailOut(
        **summary,
        normalized_title=record.normalized_title,
        announcement_type_basis=record.announcement_type_basis,
        exchange=record.exchange,
        source_page_url=record.source_page_url,
        attachment_urls=record.attachment_urls,
        is_correction=record.is_correction,
        corrected_announcement_id=record.corrected_announcement_id,
        raw_metadata_hash=record.raw_metadata_hash,
        deduplication_key=record.deduplication_key,
        fetched_at=record.fetched_at,
        first_seen_at=record.first_seen_at,
        last_seen_at=record.last_seen_at,
        source_authority_level=source.authority_level,
        source_access_mode=source.access_mode,
        redistribution_status=source.redistribution_status,
        commercial_use_status=source.commercial_use_status,
        legal_review_status=source.legal_review_status,
        source_limitations=source.limitations,
        match_evidence=candidate.match_evidence,
        document_extracted_at=candidate.document_extracted_at,
        document_limitations=candidate.document_limitations,
        reviewed_at=candidate.reviewed_at,
        dismissed_at=candidate.dismissed_at,
        imported_at=candidate.imported_at,
        information_item_id=link.information_item_id if link else None,
    )


async def patch_announcement_candidate_status(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    candidate_id: uuid.UUID,
    status: str,
    request_id: str | None,
) -> AnnouncementCandidateDetailOut:
    candidate, _record, _source = await _candidate_tuple_or_404(session, user_id=user_id, candidate_id=candidate_id)
    if candidate.status == "imported":
        raise AppError(ErrorCode.ANNOUNCEMENT_ALREADY_IMPORTED, "已导入候选不能修改处理状态", status_code=409)
    now = utc_now()
    candidate.status = status
    if status == "reviewed":
        candidate.reviewed_at = now
        action = "announcement_candidate.review"
    elif status == "dismissed":
        candidate.dismissed_at = now
        action = "announcement_candidate.dismiss"
    else:
        candidate.reviewed_at = None
        candidate.dismissed_at = None
        action = "announcement_candidate.restore"
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action=action,
        target_type="user_announcement_candidate",
        target_id=candidate.id,
        result="success",
        request_id=request_id,
    )
    await session.commit()
    return await get_announcement_candidate_detail(session, user_id=user_id, candidate_id=candidate.id)


async def extract_candidate_document(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    candidate_id: uuid.UUID,
    settings: Settings,
    request_id: str | None,
) -> AnnouncementDocumentExtractOut:
    if not settings.announcement_document_extraction_enabled:
        raise AppError(ErrorCode.ANNOUNCEMENT_FEATURE_DISABLED, "公告 PDF 提取功能未启用", status_code=403)
    candidate, record, source = await _candidate_tuple_or_404(session, user_id=user_id, candidate_id=candidate_id)
    if not record.document_url:
        raise AppError(ErrorCode.ANNOUNCEMENT_DOCUMENT_UNAVAILABLE, "该候选没有可提取 PDF 链接", status_code=422)
    try:
        extracted = await extract_announcement_pdf(record.document_url, official_domain=source.official_domain, settings=settings)
    except AppError as exc:
        candidate.document_extract_status = _document_status_from_error(exc.code)
        candidate.document_extracted_at = utc_now()
        candidate.document_limitations = [exc.message]
        await add_audit_log(
            session,
            actor_user_id=user_id,
            action="announcement_candidate.extract_pdf",
            target_type="user_announcement_candidate",
            target_id=candidate.id,
            result="failure",
            request_id=request_id,
            metadata={"error_code": exc.code.value},
        )
        await session.commit()
        raise
    candidate.document_extract_status = "succeeded"
    candidate.document_extracted_at = utc_now()
    candidate.document_page_count = extracted.page_count
    candidate.document_character_count = extracted.character_count
    candidate.document_limitations = extracted.limitations
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="announcement_candidate.extract_pdf",
        target_type="user_announcement_candidate",
        target_id=candidate.id,
        result="success",
        request_id=request_id,
        metadata={
            "page_count": extracted.page_count,
            "character_count": extracted.character_count,
            "response_bytes": extracted.response_bytes,
        },
    )
    await session.commit()
    return AnnouncementDocumentExtractOut(
        candidate_id=candidate.id,
        document_extract_status=candidate.document_extract_status,
        document_extracted_at=candidate.document_extracted_at,
        page_count=candidate.document_page_count,
        character_count=candidate.document_character_count,
        limitations=candidate.document_limitations,
    )


async def import_announcement_candidate(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    candidate_id: uuid.UUID,
    import_mode: str,
    title_override: str | None,
    user_note: str | None,
    supplemented_text: str | None,
    settings: Settings,
    request_id: str | None,
) -> AnnouncementImportOut:
    candidate, record, source = await _candidate_tuple_or_404(session, user_id=user_id, candidate_id=candidate_id)
    existing = await _ingestion_link_for_candidate(session, user_id=user_id, candidate_id=candidate.id)
    if existing:
        return AnnouncementImportOut(
            candidate_id=candidate.id,
            information_item_id=existing.information_item_id,
            import_mode=existing.import_mode,
            already_imported=True,
            created_at=existing.created_at,
        )
    text, content_origin, extraction_method, extraction_metadata = await _build_import_content(
        record=record,
        source=source,
        import_mode=import_mode,
        supplemented_text=supplemented_text,
        settings=settings,
    )
    title = normalize_whitespace(title_override or record.title)[:300]
    now = utc_now()
    item = InformationItem(
        user_id=user_id,
        input_type="manual_text",
        status="ready",
        source_type="announcement",
        title=title,
        user_note=user_note,
        is_important=False,
        is_read=False,
    )
    session.add(item)
    await session.flush()
    session.add(
        InformationSource(
            user_id=user_id,
            information_item_id=item.id,
            original_url=record.source_page_url,
            normalized_url=record.source_page_url,
            url_hash=stable_hash(f"announcement-candidate:{candidate.id}"),
            source_name=source.display_name,
            published_at=record.published_at,
            fetched_at=now if import_mode == "extracted_document" else None,
            fetch_status="skipped",
        )
    )
    session.add(
        InformationContent(
            information_item_id=item.id,
            content_version=1,
            content_origin=content_origin,
            extracted_title=title,
            extracted_text=text,
            content_hash=content_hash(text),
            character_count=len(text),
            extraction_method=extraction_method,
            extraction_status="succeeded",
            created_at=now,
        )
    )
    if candidate.matched_stock_id and candidate.match_type in {"exact_symbol", "provider_metadata", "exact_company_name"}:
        session.add(
            InformationStockRelation(
                information_item_id=item.id,
                stock_id=candidate.matched_stock_id,
                relation_origin="rule",
                relation_status="confirmed",
                relation_type="directly_related",
                confidence=None,
                evidence_text=_evidence_text(candidate),
                reviewed_at=now,
            )
        )
    link = InformationIngestionLink(
        user_id=user_id,
        information_item_id=item.id,
        external_source_id=source.id,
        source_record_type="announcement",
        announcement_record_id=record.id,
        candidate_id=candidate.id,
        imported_at=now,
        import_mode=import_mode,
        created_at=now,
    )
    session.add(link)
    candidate.status = "imported"
    candidate.imported_at = now
    if extraction_metadata:
        candidate.document_extract_status = "succeeded"
        candidate.document_extracted_at = now
        candidate.document_page_count = extraction_metadata.get("page_count")
        candidate.document_character_count = extraction_metadata.get("character_count")
        candidate.document_limitations = extraction_metadata.get("limitations", [])
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="announcement_candidate.import",
        target_type="user_announcement_candidate",
        target_id=candidate.id,
        result="success",
        request_id=request_id,
        metadata={"import_mode": import_mode, "information_item_id": str(item.id)},
    )
    from app.services.daily_reviews import mark_reviews_stale_for_information_item

    await mark_reviews_stale_for_information_item(
        session,
        user_id=user_id,
        item_id=item.id,
        settings=settings,
        reason="announcement_imported",
        request_id=request_id,
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        existing = await _ingestion_link_for_candidate(session, user_id=user_id, candidate_id=candidate.id)
        if existing:
            return AnnouncementImportOut(
                candidate_id=candidate.id,
                information_item_id=existing.information_item_id,
                import_mode=existing.import_mode,
                already_imported=True,
                created_at=existing.created_at,
            )
        raise AppError(ErrorCode.ANNOUNCEMENT_SYNC_FAILED, "公告导入失败", status_code=409) from exc
    return AnnouncementImportOut(
        candidate_id=candidate.id,
        information_item_id=item.id,
        import_mode=import_mode,
        already_imported=False,
        created_at=link.created_at,
    )


async def _get_external_source_or_404(session: AsyncSession, *, source_code: str) -> ExternalSource:
    source = (
        await session.execute(select(ExternalSource).where(ExternalSource.source_code == source_code))
    ).scalar_one_or_none()
    if not source:
        raise AppError(ErrorCode.EXTERNAL_SOURCE_NOT_FOUND, "外部来源不存在", status_code=404)
    return source


def _ensure_sync_allowed(source: ExternalSource, settings: Settings) -> None:
    if not settings.announcement_ingestion_enabled:
        raise AppError(ErrorCode.ANNOUNCEMENT_FEATURE_DISABLED, "公告候选同步功能未启用", status_code=403)
    if not settings.announcement_real_network_enabled or settings.is_production:
        raise AppError(ErrorCode.ANNOUNCEMENT_REAL_NETWORK_DISABLED, "公告真实网络同步未启用", status_code=403)
    if not source.enabled:
        raise AppError(ErrorCode.EXTERNAL_SOURCE_DISABLED, "外部来源未启用", status_code=403)
    if source.legal_review_status == "blocked" or source.health_status == "legal_hold":
        raise AppError(ErrorCode.EXTERNAL_SOURCE_LEGAL_HOLD, "外部来源处于法律阻断状态", status_code=403)
    if (
        source.authorization_status == "prohibited"
        or source.commercial_use_status == "prohibited"
        or source.redistribution_status == "prohibited"
    ):
        raise AppError(ErrorCode.EXTERNAL_SOURCE_AUTHORIZATION_REQUIRED, "外部来源授权状态不允许同步", status_code=403)


def _validate_date_range(date_from: date, date_to: date, settings: Settings) -> None:
    if date_to < date_from:
        raise AppError(ErrorCode.VALIDATION_ERROR, "结束日期不能早于开始日期", status_code=422)
    if (date_to - date_from).days > MAX_SYNC_DATE_RANGE_DAYS:
        raise AppError(ErrorCode.ANNOUNCEMENT_SYNC_LIMIT_EXCEEDED, "公告同步日期范围超过上限", status_code=422)
    earliest_allowed = date.today() - timedelta(days=max(settings.announcement_sync_lookback_days, 1))
    if date_from < earliest_allowed:
        raise AppError(ErrorCode.ANNOUNCEMENT_SYNC_LIMIT_EXCEEDED, "公告同步范围超过配置的最近日期窗口", status_code=422)


def _effective_max_records(settings: Settings, *, max_records: int | None) -> int:
    if max_records is None:
        return settings.announcement_max_records_per_run
    return max(1, min(max_records, settings.announcement_max_records_per_run))


async def _ensure_no_running_sync(session: AsyncSession, *, user_id: uuid.UUID) -> None:
    running = (
        await session.execute(
            select(ProviderSyncRun.id)
            .where(
                ProviderSyncRun.triggered_by_user_id == user_id,
                ProviderSyncRun.capability == ANNOUNCEMENT_CAPABILITY,
                ProviderSyncRun.status == "running",
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if running:
        raise AppError(ErrorCode.ANNOUNCEMENT_SYNC_ALREADY_RUNNING, "当前用户已有公告同步运行中", status_code=409)


async def _selected_watchlist(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    stock_ids: list[uuid.UUID],
    use_current_watchlist: bool,
) -> list[tuple[UserWatchlistItem, Stock]]:
    statement = (
        select(UserWatchlistItem, Stock)
        .join(Stock, Stock.id == UserWatchlistItem.stock_id)
        .where(UserWatchlistItem.user_id == user_id, UserWatchlistItem.archived_at.is_(None))
        .order_by(UserWatchlistItem.sort_order, Stock.exchange, Stock.symbol)
    )
    if not use_current_watchlist:
        unique_stock_ids = list(dict.fromkeys(stock_ids))
        if not unique_stock_ids:
            return []
        statement = statement.where(UserWatchlistItem.stock_id.in_(unique_stock_ids))
    rows = list((await session.execute(statement)).all())
    if not use_current_watchlist and len(rows) != len(set(stock_ids)):
        raise AppError(ErrorCode.WATCHLIST_ITEM_NOT_FOUND, "只能同步当前用户自选股中的股票", status_code=404)
    return rows


def _stock_symbol(stock: Stock) -> str:
    symbol = stock.symbol.upper()
    if "." in symbol:
        return symbol
    return f"{symbol}.{stock.exchange}".upper()


async def _persist_provider_result(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    source: ExternalSource,
    run: ProviderSyncRun,
    records: list[NormalizedAnnouncement],
    watchlist: list[tuple[UserWatchlistItem, Stock]],
) -> dict[str, int]:
    counts = {
        "candidate_count": 0,
        "created_record_count": 0,
        "updated_record_count": 0,
        "duplicate_record_count": 0,
    }
    watchlist_map = {_stock_symbol(stock): (item, stock) for item, stock in watchlist}
    company_map: dict[str, list[tuple[UserWatchlistItem, Stock]]] = {}
    for item, stock in watchlist:
        company_map.setdefault(stock.name.strip().lower(), []).append((item, stock))
    for normalized in records:
        record, action = await _upsert_announcement_record(session, source=source, normalized=normalized)
        counts[f"{action}_record_count"] += 1
        match = _match_candidate(record, watchlist_map, company_map)
        if not match:
            continue
        candidate = (
            await session.execute(
                select(UserAnnouncementCandidate).where(
                    UserAnnouncementCandidate.user_id == user_id,
                    UserAnnouncementCandidate.announcement_record_id == record.id,
                )
            )
        ).scalar_one_or_none()
        if not candidate:
            candidate = UserAnnouncementCandidate(
                user_id=user_id,
                announcement_record_id=record.id,
                sync_run_id=run.id,
                status="pending",
                match_type=match["match_type"],
                matched_stock_id=match.get("stock_id"),
                matched_watchlist_item_id=match.get("watchlist_item_id"),
                match_evidence=match["evidence"],
                document_extract_status="not_requested",
                document_limitations=[],
            )
            session.add(candidate)
        else:
            candidate.sync_run_id = run.id
            candidate.match_type = match["match_type"]
            candidate.matched_stock_id = match.get("stock_id")
            candidate.matched_watchlist_item_id = match.get("watchlist_item_id")
            candidate.match_evidence = match["evidence"]
        counts["candidate_count"] += 1
    return counts


async def _upsert_announcement_record(
    session: AsyncSession,
    *,
    source: ExternalSource,
    normalized: NormalizedAnnouncement,
) -> tuple[AnnouncementRecord, str]:
    statement = select(AnnouncementRecord).where(
        AnnouncementRecord.external_source_id == source.id,
        AnnouncementRecord.provider_announcement_id == normalized.provider_announcement_id,
    )
    if not normalized.provider_announcement_id:
        statement = select(AnnouncementRecord).where(
            AnnouncementRecord.external_source_id == source.id,
            AnnouncementRecord.deduplication_key == normalized.deduplication_key,
        )
    record = (await session.execute(statement.limit(1))).scalar_one_or_none()
    now = utc_now()
    if not record:
        record = AnnouncementRecord(
            external_source_id=source.id,
            source_code=source.source_code,
            provider_announcement_id=normalized.provider_announcement_id,
            title=normalized.title,
            normalized_title=normalized.normalized_title,
            announcement_type=normalized.announcement_type,
            announcement_type_confidence=normalized.announcement_type_confidence,
            announcement_type_basis=normalized.announcement_type_basis,
            published_at=normalized.published_at,
            company_name=normalized.company_name,
            stock_symbols=normalized.stock_symbols,
            exchange=normalized.exchange,
            source_page_url=normalized.source_page_url,
            document_url=normalized.document_url,
            attachment_urls=normalized.attachment_urls,
            is_pdf=normalized.is_pdf,
            is_correction=normalized.is_correction,
            corrected_announcement_id=normalized.corrected_announcement_id,
            raw_metadata_hash=normalized.raw_metadata_hash,
            deduplication_key=normalized.deduplication_key,
            data_completeness=normalized.data_completeness,
            missing_fields=normalized.missing_fields,
            fetched_at=normalized.fetched_at,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(record)
        await session.flush()
        return record, "created"
    previous_hash = record.raw_metadata_hash
    record.title = normalized.title
    record.normalized_title = normalized.normalized_title
    record.announcement_type = normalized.announcement_type
    record.announcement_type_confidence = normalized.announcement_type_confidence
    record.announcement_type_basis = normalized.announcement_type_basis
    record.published_at = normalized.published_at
    record.company_name = normalized.company_name
    record.stock_symbols = normalized.stock_symbols
    record.exchange = normalized.exchange
    record.source_page_url = normalized.source_page_url
    record.document_url = normalized.document_url
    record.attachment_urls = normalized.attachment_urls
    record.is_pdf = normalized.is_pdf
    record.is_correction = normalized.is_correction
    record.corrected_announcement_id = normalized.corrected_announcement_id
    record.raw_metadata_hash = normalized.raw_metadata_hash
    record.deduplication_key = normalized.deduplication_key
    record.data_completeness = normalized.data_completeness
    record.missing_fields = normalized.missing_fields
    record.fetched_at = normalized.fetched_at
    record.last_seen_at = now
    return record, "updated" if previous_hash != normalized.raw_metadata_hash else "duplicate"


def _match_candidate(
    record: AnnouncementRecord,
    watchlist_map: dict[str, tuple[UserWatchlistItem, Stock]],
    company_map: dict[str, list[tuple[UserWatchlistItem, Stock]]],
) -> dict[str, Any] | None:
    for symbol in record.stock_symbols:
        match = watchlist_map.get(symbol.upper())
        if match:
            item, stock = match
            return {
                "match_type": "exact_symbol",
                "stock_id": stock.id,
                "watchlist_item_id": item.id,
                "evidence": {
                    "matched_symbol": symbol,
                    "provider_symbols": record.stock_symbols,
                    "stock_name": stock.name,
                },
            }
    company_name = (record.company_name or "").strip().lower()
    if company_name and company_name in company_map:
        matches = company_map[company_name]
        if len(matches) == 1:
            item, stock = matches[0]
            return {
                "match_type": "exact_company_name",
                "stock_id": stock.id,
                "watchlist_item_id": item.id,
                "evidence": {"company_name": record.company_name, "stock_name": stock.name},
            }
        return {
            "match_type": "ambiguous_name",
            "stock_id": None,
            "watchlist_item_id": None,
            "evidence": {"company_name": record.company_name, "candidate_count": len(matches)},
        }
    return None


async def _update_sync_state(
    session: AsyncSession,
    *,
    source: ExternalSource,
    user_id: uuid.UUID,
    run: ProviderSyncRun,
    next_cursor: str | None,
) -> None:
    scope_key = _scope_key(run.requested_symbols)
    state = (
        await session.execute(
            select(ProviderSyncState).where(
                ProviderSyncState.external_source_id == source.id,
                ProviderSyncState.capability == run.capability,
                ProviderSyncState.user_id == user_id,
                ProviderSyncState.scope_type == "watchlist_symbols",
                ProviderSyncState.scope_key == scope_key,
            )
        )
    ).scalar_one_or_none()
    if not state:
        state = ProviderSyncState(
            external_source_id=source.id,
            capability=run.capability,
            user_id=user_id,
            scope_type="watchlist_symbols",
            scope_key=scope_key,
            overlap_window_seconds=86400,
            health_status="unknown",
        )
        session.add(state)
    if next_cursor:
        state.cursor_type = "published_at_plus_provider_id_with_overlap"
        state.cursor_value = next_cursor
    state.last_success_at = run.completed_at if run.status in {"complete", "partial", "data_insufficient"} else state.last_success_at
    state.last_item_published_at = _published_at_from_cursor(next_cursor) if next_cursor else state.last_item_published_at
    state.last_provider_item_id = _provider_id_from_cursor(next_cursor) if next_cursor else state.last_provider_item_id
    state.health_status = _state_health_from_run(run.status)
    state.last_error_code = run.error_code


def _scope_key(symbols: list[str]) -> str:
    return hashlib.sha256(",".join(sorted(symbols)).encode("utf-8")).hexdigest()


def _published_at_from_cursor(cursor: str | None):
    if not cursor or "|" not in cursor:
        return None
    from datetime import datetime

    try:
        return datetime.fromisoformat(cursor.split("|", 1)[0])
    except ValueError:
        return None


def _provider_id_from_cursor(cursor: str | None) -> str | None:
    if not cursor or "|" not in cursor:
        return None
    return cursor.split("|", 1)[1] or None


def _run_status_from_provider_status(status: ProviderStatus) -> str:
    if status == ProviderStatus.PASS:
        return "complete"
    if status == ProviderStatus.PARTIAL:
        return "partial"
    if status == ProviderStatus.DATA_INSUFFICIENT:
        return "data_insufficient"
    if status == ProviderStatus.DISABLED:
        return "disabled"
    if status == ProviderStatus.LEGAL_HOLD:
        return "legal_hold"
    return status.value


def _state_health_from_run(status: str) -> str:
    if status == "complete":
        return "pass"
    if status == "failed":
        return "network_error"
    return status


def _candidate_select() -> Select[tuple[UserAnnouncementCandidate, AnnouncementRecord, ExternalSource]]:
    return (
        select(UserAnnouncementCandidate, AnnouncementRecord, ExternalSource)
        .join(AnnouncementRecord, AnnouncementRecord.id == UserAnnouncementCandidate.announcement_record_id)
        .join(ExternalSource, ExternalSource.id == AnnouncementRecord.external_source_id)
    )


def _apply_candidate_filters(
    statement: Select[tuple[UserAnnouncementCandidate, AnnouncementRecord, ExternalSource]],
    *,
    source_code: str | None,
    stock_id: uuid.UUID | None,
    announcement_type: str | None,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
) -> Select[tuple[UserAnnouncementCandidate, AnnouncementRecord, ExternalSource]]:
    if source_code:
        statement = statement.where(ExternalSource.source_code == source_code)
    if stock_id:
        statement = statement.where(UserAnnouncementCandidate.matched_stock_id == stock_id)
    if announcement_type:
        statement = statement.where(AnnouncementRecord.announcement_type == announcement_type)
    if date_from:
        statement = statement.where(func.date(AnnouncementRecord.published_at) >= date_from)
    if date_to:
        statement = statement.where(func.date(AnnouncementRecord.published_at) <= date_to)
    if q:
        like = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                AnnouncementRecord.title.ilike(like),
                AnnouncementRecord.company_name.ilike(like),
            )
        )
    return statement


async def _candidate_tuple_or_404(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> tuple[UserAnnouncementCandidate, AnnouncementRecord, ExternalSource]:
    row = (
        await session.execute(
            _candidate_select().where(
                UserAnnouncementCandidate.id == candidate_id,
                UserAnnouncementCandidate.user_id == user_id,
            )
        )
    ).one_or_none()
    if not row:
        raise AppError(ErrorCode.ANNOUNCEMENT_CANDIDATE_NOT_FOUND, "公告候选不存在", status_code=404)
    return row


async def _ingestion_link_for_candidate(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> InformationIngestionLink | None:
    return (
        await session.execute(
            select(InformationIngestionLink).where(
                InformationIngestionLink.user_id == user_id,
                InformationIngestionLink.candidate_id == candidate_id,
            )
        )
    ).scalar_one_or_none()


def _candidate_summary_out(
    candidate: UserAnnouncementCandidate,
    record: AnnouncementRecord,
    source: ExternalSource,
) -> AnnouncementCandidateSummaryOut:
    return AnnouncementCandidateSummaryOut(
        id=candidate.id,
        announcement_record_id=record.id,
        sync_run_id=candidate.sync_run_id,
        status=candidate.status,
        match_type=candidate.match_type,
        matched_stock_id=candidate.matched_stock_id,
        matched_watchlist_item_id=candidate.matched_watchlist_item_id,
        title=record.title,
        announcement_type=record.announcement_type,
        announcement_type_confidence=record.announcement_type_confidence,
        published_at=record.published_at,
        company_name=record.company_name,
        stock_symbols=record.stock_symbols,
        source_code=source.source_code,
        source_display_name=source.display_name,
        source_tier=source.source_tier,
        authorization_status=source.authorization_status,
        data_completeness=record.data_completeness,
        missing_fields=record.missing_fields,
        is_pdf=record.is_pdf,
        document_url=record.document_url,
        document_extract_status=candidate.document_extract_status,
        document_page_count=candidate.document_page_count,
        document_character_count=candidate.document_character_count,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


def _document_status_from_error(code: ErrorCode) -> str:
    mapping = {
        ErrorCode.ANNOUNCEMENT_DOCUMENT_UNAVAILABLE: "unavailable",
        ErrorCode.ANNOUNCEMENT_DOCUMENT_TOO_LARGE: "too_large",
        ErrorCode.ANNOUNCEMENT_DOCUMENT_TOO_MANY_PAGES: "too_many_pages",
        ErrorCode.ANNOUNCEMENT_DOCUMENT_TEXT_UNAVAILABLE: "text_unavailable",
    }
    return mapping.get(code, "failed")


async def _build_import_content(
    *,
    record: AnnouncementRecord,
    source: ExternalSource,
    import_mode: str,
    supplemented_text: str | None,
    settings: Settings,
) -> tuple[str, str, str, dict[str, Any]]:
    if import_mode == "metadata_only":
        return _metadata_only_text(record, source), "user_input", "announcement_metadata_import", {}
    if import_mode == "user_supplemented":
        text = normalize_whitespace(supplemented_text or "")
        if not text:
            raise AppError(ErrorCode.INFORMATION_CONTENT_REQUIRED, "补充文本不能为空", status_code=422)
        return text, "user_correction", "announcement_user_supplement", {}
    if import_mode == "extracted_document":
        if not settings.announcement_document_extraction_enabled:
            raise AppError(ErrorCode.ANNOUNCEMENT_FEATURE_DISABLED, "公告 PDF 提取功能未启用", status_code=403)
        if not record.document_url:
            raise AppError(ErrorCode.ANNOUNCEMENT_DOCUMENT_UNAVAILABLE, "该公告没有可提取 PDF 链接", status_code=422)
        extracted = await extract_announcement_pdf(record.document_url, official_domain=source.official_domain, settings=settings)
        return (
            extracted.text,
            "provider_document",
            "announcement_pdf_pypdf",
            {
                "page_count": extracted.page_count,
                "character_count": extracted.character_count,
                "limitations": extracted.limitations,
            },
        )
    raise AppError(ErrorCode.ANNOUNCEMENT_IMPORT_MODE_INVALID, "公告导入模式无效", status_code=422)


def _metadata_only_text(record: AnnouncementRecord, source: ExternalSource) -> str:
    lines = [
        "【公告元数据导入】",
        "当前仅导入公告元数据，未提取、补写或长期保存公告 PDF 原文。",
        f"标题：{record.title}",
        f"公司：{record.company_name or '未知'}",
        f"股票：{', '.join(record.stock_symbols) if record.stock_symbols else '未确认'}",
        f"公告类型：{record.announcement_type}",
        f"发布时间：{record.published_at.isoformat() if record.published_at else '未知'}",
        f"来源：{source.display_name}",
        f"官方页面：{record.source_page_url}",
    ]
    if record.document_url:
        lines.append(f"PDF链接：{record.document_url}")
    lines.append("限制：来源授权、完整性、及时性、稳定性及长期可用性尚未最终确认。")
    return "\n".join(lines)


def _evidence_text(candidate: UserAnnouncementCandidate) -> str:
    evidence = candidate.match_evidence or {}
    if candidate.match_type == "exact_symbol":
        return f"公告候选按证券代码精确匹配：{evidence.get('matched_symbol')}"
    if candidate.match_type == "exact_company_name":
        return f"公告候选按公司名称精确匹配：{evidence.get('company_name')}"
    return f"公告候选规则匹配：{candidate.match_type}"


def sync_run_out(run: ProviderSyncRun) -> ProviderSyncRunOut:
    return ProviderSyncRunOut.model_validate(run)
