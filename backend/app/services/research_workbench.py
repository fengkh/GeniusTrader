import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.models.ai import AITask
from app.models.external_source import AnnouncementRecord, UserAnnouncementCandidate
from app.models.information import (
    InformationAnalysisVersion,
    InformationItem,
    InformationSource,
    InformationStockRelation,
)
from app.models.research import ResearchTask, ResearchTaskUpdate
from app.models.review_notification import DailyReview, DailyReviewVersion
from app.models.tag import UserTag, WatchlistItemTag
from app.models.watchlist import UserWatchlistItem
from app.schemas.research import ResearchTaskOut
from app.schemas.stock import StockRead
from app.schemas.watchlist import UserTagRead, WatchlistGroupRead
from app.schemas.workbench import (
    LatestReviewOut,
    OfficialInformationOut,
    PriorityStockOut,
    ReviewHistoryOut,
    StockCurrentStateOut,
    StockResearchDossierOut,
    TimelineEntryOut,
    TodayActionItemOut,
    TodayObservationConditionOut,
    TodayOverviewOut,
    TodayOverviewStats,
    WatchlistProfileOut,
    WatchlistScannerOut,
    WatchlistScannerRowOut,
)
from app.services.market_data import (
    get_market_data_status,
    get_stock_market_snapshot,
    get_watchlist_market_snapshots,
)
from app.services.research_tasks import OPEN_RESEARCH_TASK_STATUSES, create_due_research_task_events


async def build_today_overview(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    business_date: date,
    settings: Settings,
    request_id: str | None,
) -> TodayOverviewOut:
    await create_due_research_task_events(
        session,
        user_id=user_id,
        business_date=business_date,
        request_id=request_id,
    )
    await session.commit()
    watchlist_items = await _watchlist_items(session, user_id)
    stock_ids = [item.stock_id for item in watchlist_items]
    market_status = await get_market_data_status(session, settings=settings)
    snapshots = {row.watchlist_item_id: row for row in await get_watchlist_market_snapshots(session, user_id=user_id)}
    market_summary = _market_summary(list(snapshots.values()))

    new_info_counts = await _information_counts_by_stock(
        session,
        user_id=user_id,
        stock_ids=stock_ids,
        date_from=business_date,
        date_to=business_date,
    )
    info_needing_analysis_count = await _information_needing_analysis_count(
        session,
        user_id=user_id,
        business_date=business_date,
    )
    official_counts = await _official_information_counts_by_stock(
        session,
        user_id=user_id,
        stock_ids=stock_ids,
        date_from=business_date,
        date_to=business_date,
    )
    pending_candidate_counts = await _pending_candidate_counts_by_stock(session, user_id=user_id, stock_ids=stock_ids)
    new_candidate_count = await _new_candidate_count(session, user_id=user_id, business_date=business_date)
    task_counts = await _task_counts_by_stock(session, user_id=user_id, stock_ids=stock_ids, business_date=business_date)
    open_task_count = await _task_count(session, user_id=user_id, open_only=True)
    due_observation_count = await _due_observation_count(session, user_id=user_id, business_date=business_date)
    review = await _review_for_date(session, user_id=user_id, business_date=business_date)
    latest_version_number = await _latest_review_version_number(session, review.id) if review else None
    stale_review_count = await _stale_review_count(session, user_id=user_id, business_date=business_date)
    generation_in_progress = await _generation_in_progress(session, user_id=user_id, review_id=review.id if review else None)

    priority_stocks: list[PriorityStockOut] = []
    for item in watchlist_items:
        counts = task_counts.get(item.stock_id, {})
        market_row = snapshots.get(item.id)
        quote_fields = _market_quote_fields(market_row)
        priority_quote_fields = {
            key: quote_fields[key]
            for key in ["close", "pct_change", "amount", "turnover_rate", "trade_date", "source_code", "freshness_status"]
        }
        reasons: list[str] = []
        score = 0
        if official_counts.get(item.stock_id, 0):
            score += 3
            reasons.append(f"今日有新官方公告 {official_counts[item.stock_id]} 条")
        if pending_candidate_counts.get(item.stock_id, 0):
            score += 2
            reasons.append(f"有待审核公告候选 {pending_candidate_counts[item.stock_id]} 条")
        if review and review.status == "stale":
            score += 2
            reasons.append("当日复盘需要更新")
        if counts.get("high_verification", 0):
            score += 3
            reasons.append(f"高优先级待核实 {counts['high_verification']} 项")
        if counts.get("verification", 0):
            score += 1
            reasons.append(f"待核实事项 {counts['verification']} 项")
        if counts.get("due_observation", 0):
            score += 2
            reasons.append(f"到期观察条件 {counts['due_observation']} 项")
        if new_info_counts.get(item.stock_id, 0):
            score += 1
            reasons.append(f"今日新增信息 {new_info_counts[item.stock_id]} 条")
        if quote_fields["pct_change"] is not None and abs(quote_fields["pct_change"]) >= Decimal("5"):
            score += 1
            reasons.append(f"真实日级行情涨跌幅达到 5% 阈值：{quote_fields['pct_change']}%")
        priority_stocks.append(
            PriorityStockOut(
                stock_id=item.stock_id,
                symbol=item.stock.symbol,
                name=item.stock.name,
                priority_score=score,
                priority_reasons=reasons or ["暂无需要优先处理的变化"],
                new_information_count=new_info_counts.get(item.stock_id, 0),
                pending_candidate_count=pending_candidate_counts.get(item.stock_id, 0),
                open_task_count=counts.get("open", 0),
                due_observation_count=counts.get("due_observation", 0),
                review_status=review.status if review else None,
                latest_market_snapshot=market_row,
                **priority_quote_fields,
            )
        )
    priority_stocks.sort(key=lambda row: (-row.priority_score, row.symbol))

    observation_conditions = await _due_observation_rows(
        session,
        user_id=user_id,
        business_date=business_date,
    )
    action_items = [
        TodayActionItemOut(
            count=sum(pending_candidate_counts.values()),
            target_url="/information/announcements",
            severity="notice",
            title="待审核公告",
        ),
        TodayActionItemOut(
            count=info_needing_analysis_count,
            target_url="/information",
            severity="notice",
            title="待分析信息",
        ),
        TodayActionItemOut(
            count=stale_review_count,
            target_url="/reviews",
            severity="notice",
            title="stale复盘",
        ),
        TodayActionItemOut(
            count=await _task_count(session, user_id=user_id, task_type="verification", open_only=True),
            target_url="/information/tasks?task_type=verification",
            severity="important",
            title="待核实事项",
        ),
        TodayActionItemOut(
            count=due_observation_count,
            target_url="/information/tasks?task_type=observation&open_only=true",
            severity="important",
            title="今日观察条件",
        ),
        TodayActionItemOut(
            count=await _task_count(session, user_id=user_id, task_type="missing_document", open_only=True),
            target_url="/information/tasks?task_type=missing_document",
            severity="notice",
            title="正文缺失事项",
        ),
    ]
    overview = TodayOverviewStats(
        business_date=business_date,
        watchlist_count=len(watchlist_items),
        market_trade_date=market_summary["market_trade_date"],
        market_snapshot_count=market_summary["market_snapshot_count"],
        market_data_available_count=market_summary["market_data_available_count"],
        market_data_unavailable_count=market_summary["market_data_unavailable_count"],
        gainers_count=market_summary["gainers_count"],
        decliners_count=market_summary["decliners_count"],
        unchanged_count=market_summary["unchanged_count"],
        stocks_with_new_information=sum(1 for value in new_info_counts.values() if value > 0),
        new_announcement_candidate_count=new_candidate_count,
        pending_announcement_candidate_count=sum(pending_candidate_counts.values()),
        stale_review_count=stale_review_count,
        open_research_task_count=open_task_count,
        due_observation_count=due_observation_count,
        information_needing_analysis_count=info_needing_analysis_count,
        latest_review_status=review.status if review else None,
        market_data_status=_market_data_status(market_summary, market_status.latest_trade_date),
    )
    return TodayOverviewOut(
        overview=overview,
        priority_stocks=priority_stocks[:20],
        action_items=action_items,
        observation_conditions=observation_conditions,
        latest_review=LatestReviewOut(
            review_id=review.id if review else None,
            review_date=review.review_date if review else None,
            status=review.status if review else None,
            stale=bool(review and review.status == "stale"),
            version=latest_version_number,
            generation_in_progress=generation_in_progress,
        ),
    )


async def build_watchlist_scanner(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    keyword: str | None,
    group_id: uuid.UUID | None,
    tag_id: uuid.UUID | None,
    has_new_information: bool | None,
    has_pending_candidate: bool | None,
    has_open_task: bool | None,
    has_high_priority_task: bool | None,
    has_observation: bool | None,
    review_stale: bool | None,
    market_data_available: bool | None,
    market_movement: str | None,
    exchange: str | None,
    sort: str,
    settings: Settings,
) -> WatchlistScannerOut:
    business_date = _business_today(settings)
    items = await _watchlist_items(session, user_id)
    if group_id:
        items = [item for item in items if item.group_id == group_id]
    if tag_id:
        tagged = set(
            (
                await session.execute(
                    select(WatchlistItemTag.watchlist_item_id).where(WatchlistItemTag.tag_id == tag_id)
                )
            )
            .scalars()
            .all()
        )
        items = [item for item in items if item.id in tagged]
    if exchange:
        items = [item for item in items if item.stock.exchange == exchange]
    if keyword:
        text = keyword.strip().lower()
        items = [
            item
            for item in items
            if text in item.stock.symbol.lower()
            or text in item.stock.code.lower()
            or text in item.stock.name.lower()
            or text in (item.attention_reason or "").lower()
        ]
    stock_ids = [item.stock_id for item in items]
    tags = await _tag_map(session, user_id=user_id, item_ids=[item.id for item in items])
    snapshots = {row.watchlist_item_id: row for row in await get_watchlist_market_snapshots(session, user_id=user_id)}
    new_info = await _information_counts_by_stock(
        session,
        user_id=user_id,
        stock_ids=stock_ids,
        date_from=business_date,
        date_to=business_date,
    )
    official_7d = await _official_information_counts_by_stock(
        session,
        user_id=user_id,
        stock_ids=stock_ids,
        date_from=business_date - timedelta(days=7),
        date_to=business_date,
    )
    pending_candidates = await _pending_candidate_counts_by_stock(session, user_id=user_id, stock_ids=stock_ids)
    task_counts = await _task_counts_by_stock(session, user_id=user_id, stock_ids=stock_ids, business_date=business_date)
    last_info = await _last_information_at_by_stock(session, user_id=user_id, stock_ids=stock_ids)
    latest_review = await _latest_review_for_user(session, user_id=user_id)
    rows: list[WatchlistScannerRowOut] = []
    for item in items:
        counts = task_counts.get(item.stock_id, {})
        snapshot = snapshots.get(item.id)
        quote_fields = _market_quote_fields(snapshot)
        reasons: list[str] = []
        score = 0
        if new_info.get(item.stock_id, 0):
            score += 2
            reasons.append(f"今日新增信息 {new_info[item.stock_id]} 条")
        if official_7d.get(item.stock_id, 0):
            score += 2
            reasons.append(f"7日官方信息 {official_7d[item.stock_id]} 条")
        if pending_candidates.get(item.stock_id, 0):
            score += 2
            reasons.append(f"待审核公告 {pending_candidates[item.stock_id]} 条")
        if counts.get("high", 0):
            score += 3
            reasons.append(f"高优先级事项 {counts['high']} 项")
        if counts.get("open", 0):
            score += 1
            reasons.append(f"打开事项 {counts['open']} 项")
        if latest_review and latest_review.status == "stale":
            score += 1
            reasons.append("最新复盘需要更新")
        rows.append(
            WatchlistScannerRowOut(
                watchlist_item_id=item.id,
                stock_id=item.stock_id,
                symbol=item.stock.symbol,
                name=item.stock.name,
                exchange=item.stock.exchange,
                group=WatchlistGroupRead.model_validate(item.group) if item.group else None,
                tags=tags.get(item.id, []),
                focus_reason=item.attention_reason,
                latest_market_snapshot=snapshot,
                **quote_fields,
                new_information_count=new_info.get(item.stock_id, 0),
                official_announcement_count_7d=official_7d.get(item.stock_id, 0),
                pending_candidate_count=pending_candidates.get(item.stock_id, 0),
                open_verification_count=counts.get("verification", 0),
                open_observation_count=counts.get("observation", 0),
                high_priority_task_count=counts.get("high", 0),
                review_status=latest_review.status if latest_review else None,
                latest_review_date=latest_review.review_date if latest_review else None,
                stale=bool(latest_review and latest_review.status == "stale"),
                last_information_at=last_info.get(item.stock_id),
                attention_score=score,
                attention_reasons=reasons or ["暂无新增研究信号"],
            )
        )
    rows = _filter_scanner_rows(
        rows,
        has_new_information=has_new_information,
        has_pending_candidate=has_pending_candidate,
        has_open_task=has_open_task,
        has_high_priority_task=has_high_priority_task,
        has_observation=has_observation,
        review_stale=review_stale,
        market_data_available=market_data_available,
        market_movement=market_movement,
    )
    rows.sort(key=_scanner_sort_key(sort))
    return WatchlistScannerOut(items=rows, total=len(rows))


async def build_stock_research_dossier(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    stock_id: uuid.UUID,
    settings: Settings,
) -> StockResearchDossierOut:
    item = (
        await session.execute(
            select(UserWatchlistItem)
            .options(selectinload(UserWatchlistItem.stock), selectinload(UserWatchlistItem.group))
            .where(
                UserWatchlistItem.user_id == user_id,
                UserWatchlistItem.stock_id == stock_id,
                UserWatchlistItem.archived_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise AppError(ErrorCode.WATCHLIST_ITEM_NOT_FOUND, "自选股不存在", status_code=404)
    tags = await _tag_map(session, user_id=user_id, item_ids=[item.id])
    market = await get_stock_market_snapshot(session, stock_id=stock_id)
    business_date = _business_today(settings)
    new_info = await _information_counts_by_stock(
        session,
        user_id=user_id,
        stock_ids=[stock_id],
        date_from=business_date,
        date_to=business_date,
    )
    pending_candidates = await _pending_candidate_counts_by_stock(session, user_id=user_id, stock_ids=[stock_id])
    task_counts = await _task_counts_by_stock(session, user_id=user_id, stock_ids=[stock_id], business_date=business_date)
    latest_review = await _latest_review_for_user(session, user_id=user_id)
    official_information = await _official_information_rows(session, user_id=user_id, stock_id=stock_id)
    tasks = await _tasks_for_stock(session, user_id=user_id, stock_id=stock_id)
    timeline = await _stock_timeline(session, user_id=user_id, stock_id=stock_id, tasks=tasks)
    review_history = await _review_history(session, user_id=user_id, stock_id=stock_id)
    return StockResearchDossierOut(
        identity=StockRead.model_validate(item.stock),
        watchlist_profile=WatchlistProfileOut(
            group=WatchlistGroupRead.model_validate(item.group) if item.group else None,
            tags=tags.get(item.id, []),
            focus_reason=item.attention_reason,
            user_notes=item.notes,
            created_at=item.created_at,
            updated_at=item.updated_at,
        ),
        market_snapshot=market,
        current_state=StockCurrentStateOut(
            new_information_count=new_info.get(stock_id, 0),
            pending_candidate_count=pending_candidates.get(stock_id, 0),
            open_task_count=task_counts.get(stock_id, {}).get("open", 0),
            observation_count=task_counts.get(stock_id, {}).get("observation", 0),
            latest_review_status=latest_review.status if latest_review else None,
            stale=bool(latest_review and latest_review.status == "stale"),
        ),
        official_information=official_information,
        research_tasks=[ResearchTaskOut.model_validate(task) for task in tasks],
        timeline=timeline,
        review_history=review_history,
        data_boundaries=[
            "暂无经授权的真实行情数据时，不展示 0 元、0% 或 Mock K 线。",
            "时间轴由程序合并排序，不调用 AI 生成事件。",
            "AI 建议必须由用户确认后才成为研究事项。",
        ],
    )


async def _watchlist_items(session: AsyncSession, user_id: uuid.UUID) -> list[UserWatchlistItem]:
    return list(
        (
            await session.execute(
                select(UserWatchlistItem)
                .options(selectinload(UserWatchlistItem.stock), selectinload(UserWatchlistItem.group))
                .where(UserWatchlistItem.user_id == user_id, UserWatchlistItem.archived_at.is_(None))
                .order_by(UserWatchlistItem.sort_order.asc(), UserWatchlistItem.created_at.asc())
            )
        )
        .scalars()
        .all()
    )


async def _tag_map(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    item_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[UserTagRead]]:
    if not item_ids:
        return {}
    rows = (
        await session.execute(
            select(WatchlistItemTag.watchlist_item_id, UserTag)
            .join(UserTag, UserTag.id == WatchlistItemTag.tag_id)
            .where(UserTag.user_id == user_id, WatchlistItemTag.watchlist_item_id.in_(item_ids))
            .order_by(UserTag.name)
        )
    ).all()
    result: dict[uuid.UUID, list[UserTagRead]] = defaultdict(list)
    for item_id, tag in rows:
        result[item_id].append(UserTagRead.model_validate(tag))
    return result


async def _information_counts_by_stock(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    stock_ids: list[uuid.UUID],
    date_from: date,
    date_to: date,
) -> dict[uuid.UUID, int]:
    if not stock_ids:
        return {}
    start, end = _date_window(date_from, date_to, "Asia/Shanghai")
    rows = (
        await session.execute(
            select(InformationStockRelation.stock_id, func.count(func.distinct(InformationItem.id)))
            .join(InformationItem, InformationItem.id == InformationStockRelation.information_item_id)
            .outerjoin(InformationSource, InformationSource.information_item_id == InformationItem.id)
            .where(
                InformationItem.user_id == user_id,
                InformationItem.archived_at.is_(None),
                InformationStockRelation.stock_id.in_(stock_ids),
                InformationStockRelation.relation_status == "confirmed",
                func.coalesce(InformationSource.published_at, InformationItem.created_at) >= start,
                func.coalesce(InformationSource.published_at, InformationItem.created_at) < end,
            )
            .group_by(InformationStockRelation.stock_id)
        )
    ).all()
    return {stock_id: int(count) for stock_id, count in rows}


async def _official_information_counts_by_stock(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    stock_ids: list[uuid.UUID],
    date_from: date,
    date_to: date,
) -> dict[uuid.UUID, int]:
    if not stock_ids:
        return {}
    start, end = _date_window(date_from, date_to, "Asia/Shanghai")
    rows = (
        await session.execute(
            select(InformationStockRelation.stock_id, func.count(func.distinct(InformationItem.id)))
            .join(InformationItem, InformationItem.id == InformationStockRelation.information_item_id)
            .outerjoin(InformationSource, InformationSource.information_item_id == InformationItem.id)
            .where(
                InformationItem.user_id == user_id,
                InformationItem.archived_at.is_(None),
                InformationItem.source_type == "announcement",
                InformationStockRelation.stock_id.in_(stock_ids),
                InformationStockRelation.relation_status == "confirmed",
                func.coalesce(InformationSource.published_at, InformationItem.created_at) >= start,
                func.coalesce(InformationSource.published_at, InformationItem.created_at) < end,
            )
            .group_by(InformationStockRelation.stock_id)
        )
    ).all()
    return {stock_id: int(count) for stock_id, count in rows}


async def _pending_candidate_counts_by_stock(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    stock_ids: list[uuid.UUID],
) -> dict[uuid.UUID, int]:
    if not stock_ids:
        return {}
    rows = (
        await session.execute(
            select(UserAnnouncementCandidate.matched_stock_id, func.count())
            .where(
                UserAnnouncementCandidate.user_id == user_id,
                UserAnnouncementCandidate.status == "pending",
                UserAnnouncementCandidate.matched_stock_id.in_(stock_ids),
            )
            .group_by(UserAnnouncementCandidate.matched_stock_id)
        )
    ).all()
    return {stock_id: int(count) for stock_id, count in rows if stock_id}


async def _new_candidate_count(session: AsyncSession, *, user_id: uuid.UUID, business_date: date) -> int:
    start, end = _date_window(business_date, business_date, "Asia/Shanghai")
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(UserAnnouncementCandidate)
                .where(
                    UserAnnouncementCandidate.user_id == user_id,
                    UserAnnouncementCandidate.created_at >= start,
                    UserAnnouncementCandidate.created_at < end,
                )
            )
        ).scalar_one()
    )


async def _task_counts_by_stock(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    stock_ids: list[uuid.UUID],
    business_date: date,
) -> dict[uuid.UUID, dict[str, int]]:
    result: dict[uuid.UUID, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    if not stock_ids:
        return {}
    rows = list(
        (
            await session.execute(
                select(ResearchTask).where(
                    ResearchTask.user_id == user_id,
                    ResearchTask.stock_id.in_(stock_ids),
                    ResearchTask.status.in_(OPEN_RESEARCH_TASK_STATUSES),
                )
            )
        )
        .scalars()
        .all()
    )
    for task in rows:
        if task.stock_id is None:
            continue
        bucket = result[task.stock_id]
        bucket["open"] += 1
        if task.task_type == "verification":
            bucket["verification"] += 1
            if task.priority == "high":
                bucket["high_verification"] += 1
        if task.task_type == "observation":
            bucket["observation"] += 1
            if task.due_date and task.due_date <= business_date:
                bucket["due_observation"] += 1
        if task.priority == "high":
            bucket["high"] += 1
    return {key: dict(value) for key, value in result.items()}


async def _task_count(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    task_type: str | None = None,
    open_only: bool = False,
) -> int:
    statement = select(func.count()).select_from(ResearchTask).where(ResearchTask.user_id == user_id)
    if task_type:
        statement = statement.where(ResearchTask.task_type == task_type)
    if open_only:
        statement = statement.where(ResearchTask.status.in_(OPEN_RESEARCH_TASK_STATUSES))
    return int((await session.execute(statement)).scalar_one())


async def _due_observation_count(session: AsyncSession, *, user_id: uuid.UUID, business_date: date) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(ResearchTask)
                .where(
                    ResearchTask.user_id == user_id,
                    ResearchTask.task_type == "observation",
                    ResearchTask.status.in_(OPEN_RESEARCH_TASK_STATUSES),
                    ResearchTask.due_date.is_not(None),
                    ResearchTask.due_date <= business_date,
                )
            )
        ).scalar_one()
    )


async def _due_observation_rows(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    business_date: date,
) -> list[TodayObservationConditionOut]:
    rows = list(
        (
            await session.execute(
                select(ResearchTask)
                .options(selectinload(ResearchTask.stock))
                .where(
                    ResearchTask.user_id == user_id,
                    ResearchTask.task_type == "observation",
                    ResearchTask.status.in_(OPEN_RESEARCH_TASK_STATUSES),
                    ResearchTask.due_date.is_not(None),
                    ResearchTask.due_date <= business_date,
                )
                .order_by(ResearchTask.due_date.asc(), ResearchTask.priority.desc(), ResearchTask.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [
        TodayObservationConditionOut(
            task_id=task.id,
            stock=StockRead.model_validate(task.stock) if task.stock else None,
            title=task.title,
            due_date=task.due_date,
            status=task.status,
            source_review=str(task.source_daily_review_id) if task.source_daily_review_id else None,
        )
        for task in rows
    ]


async def _information_needing_analysis_count(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    business_date: date,
) -> int:
    start, end = _date_window(business_date, business_date, "Asia/Shanghai")
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(InformationItem)
                .where(
                    InformationItem.user_id == user_id,
                    InformationItem.archived_at.is_(None),
                    InformationItem.status.in_(("ready", "analysis_failed")),
                    InformationItem.created_at >= start,
                    InformationItem.created_at < end,
                )
            )
        ).scalar_one()
    )


async def _review_for_date(session: AsyncSession, *, user_id: uuid.UUID, business_date: date) -> DailyReview | None:
    return (
        await session.execute(
            select(DailyReview).where(
                DailyReview.user_id == user_id,
                DailyReview.review_date == business_date,
                DailyReview.archived_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def _latest_review_for_user(session: AsyncSession, *, user_id: uuid.UUID) -> DailyReview | None:
    return (
        await session.execute(
            select(DailyReview)
            .where(DailyReview.user_id == user_id, DailyReview.archived_at.is_(None))
            .order_by(DailyReview.review_date.desc(), DailyReview.updated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _latest_review_version_number(session: AsyncSession, review_id: uuid.UUID) -> int | None:
    return (
        await session.execute(
            select(func.max(DailyReviewVersion.version_number)).where(DailyReviewVersion.daily_review_id == review_id)
        )
    ).scalar_one()


async def _stale_review_count(session: AsyncSession, *, user_id: uuid.UUID, business_date: date) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(DailyReview)
                .where(
                    DailyReview.user_id == user_id,
                    DailyReview.review_date <= business_date,
                    DailyReview.status == "stale",
                    DailyReview.archived_at.is_(None),
                )
            )
        ).scalar_one()
    )


async def _generation_in_progress(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    review_id: uuid.UUID | None,
) -> bool:
    if not review_id:
        return False
    count = (
        await session.execute(
            select(func.count())
            .select_from(AITask)
            .where(
                AITask.user_id == user_id,
                AITask.task_type == "user_daily_review_generation",
                AITask.target_type == "daily_review",
                AITask.target_id == review_id,
                AITask.status.in_(("pending", "running")),
            )
        )
    ).scalar_one()
    return count > 0


async def _last_information_at_by_stock(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    stock_ids: list[uuid.UUID],
) -> dict[uuid.UUID, datetime]:
    if not stock_ids:
        return {}
    rows = (
        await session.execute(
            select(InformationStockRelation.stock_id, func.max(InformationItem.created_at))
            .join(InformationItem, InformationItem.id == InformationStockRelation.information_item_id)
            .where(
                InformationItem.user_id == user_id,
                InformationItem.archived_at.is_(None),
                InformationStockRelation.stock_id.in_(stock_ids),
                InformationStockRelation.relation_status == "confirmed",
            )
            .group_by(InformationStockRelation.stock_id)
        )
    ).all()
    return {stock_id: value for stock_id, value in rows if value}


def _filter_scanner_rows(
    rows: list[WatchlistScannerRowOut],
    *,
    has_new_information: bool | None,
    has_pending_candidate: bool | None,
    has_open_task: bool | None,
    has_high_priority_task: bool | None,
    has_observation: bool | None,
    review_stale: bool | None,
    market_data_available: bool | None,
    market_movement: str | None,
) -> list[WatchlistScannerRowOut]:
    result = rows
    if has_new_information is not None:
        result = [row for row in result if (row.new_information_count > 0) == has_new_information]
    if has_pending_candidate is not None:
        result = [row for row in result if (row.pending_candidate_count > 0) == has_pending_candidate]
    if has_open_task is not None:
        result = [
            row
            for row in result
            if ((row.open_verification_count + row.open_observation_count) > 0) == has_open_task
        ]
    if has_high_priority_task is not None:
        result = [row for row in result if (row.high_priority_task_count > 0) == has_high_priority_task]
    if has_observation is not None:
        result = [row for row in result if (row.open_observation_count > 0) == has_observation]
    if review_stale is not None:
        result = [row for row in result if row.stale == review_stale]
    if market_data_available is not None:
        result = [
            row
            for row in result
            if bool(row.latest_market_snapshot and row.latest_market_snapshot.snapshot is not None)
            == market_data_available
        ]
    if market_movement:
        if market_movement == "up":
            result = [row for row in result if row.pct_change is not None and row.pct_change > 0]
        elif market_movement == "down":
            result = [row for row in result if row.pct_change is not None and row.pct_change < 0]
        elif market_movement == "unchanged":
            result = [row for row in result if row.pct_change is not None and row.pct_change == 0]
    return result


def _scanner_sort_key(sort: str):
    def by_value(row: WatchlistScannerRowOut):
        normalized_sort = "attention_score" if sort == "attention" else sort
        if sort == "last_information_at":
            return (row.last_information_at is None, row.last_information_at or datetime.min.replace(tzinfo=UTC))
        if sort == "pending_candidate_count":
            return (-row.pending_candidate_count, row.symbol)
        if sort == "open_task_count":
            return (-(row.open_verification_count + row.open_observation_count), row.symbol)
        if sort == "latest_review_date":
            return (row.latest_review_date is None, row.latest_review_date or date.min, row.symbol)
        if normalized_sort in {"symbol", "name"}:
            return (row.symbol,)
        if normalized_sort in {"pct_change", "amount", "turnover_rate"}:
            value = getattr(row, normalized_sort)
            return (value is None, -(value or Decimal("0")), row.symbol)
        return (-row.attention_score, row.symbol)

    return by_value


async def _official_information_rows(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    stock_id: uuid.UUID,
) -> list[OfficialInformationOut]:
    rows = list(
        (
            await session.execute(
                select(InformationItem)
                .join(InformationStockRelation, InformationStockRelation.information_item_id == InformationItem.id)
                .where(
                    InformationItem.user_id == user_id,
                    InformationItem.source_type == "announcement",
                    InformationItem.archived_at.is_(None),
                    InformationStockRelation.stock_id == stock_id,
                    InformationStockRelation.relation_status == "confirmed",
                )
                .order_by(InformationItem.created_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    return [
        OfficialInformationOut(
            id=item.id,
            title=item.title,
            source_type=item.source_type,
            status=item.status,
            is_important=item.is_important,
            created_at=item.created_at,
            target_url=f"/information/items/{item.id}",
        )
        for item in rows
    ]


async def _tasks_for_stock(session: AsyncSession, *, user_id: uuid.UUID, stock_id: uuid.UUID) -> list[ResearchTask]:
    return list(
        (
            await session.execute(
                select(ResearchTask)
                .options(selectinload(ResearchTask.stock), selectinload(ResearchTask.updates))
                .where(ResearchTask.user_id == user_id, ResearchTask.stock_id == stock_id)
                .order_by(ResearchTask.status, ResearchTask.due_date.asc().nullslast(), ResearchTask.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def _stock_timeline(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    stock_id: uuid.UUID,
    tasks: list[ResearchTask],
) -> list[TimelineEntryOut]:
    entries: list[TimelineEntryOut] = []
    candidates = list(
        (
            await session.execute(
                select(UserAnnouncementCandidate, AnnouncementRecord)
                .join(AnnouncementRecord, AnnouncementRecord.id == UserAnnouncementCandidate.announcement_record_id)
                .where(UserAnnouncementCandidate.user_id == user_id, UserAnnouncementCandidate.matched_stock_id == stock_id)
                .order_by(UserAnnouncementCandidate.created_at.desc())
                .limit(20)
            )
        ).all()
    )
    for candidate, record in candidates:
        entries.append(
            TimelineEntryOut(
                event_type="announcement_candidate",
                occurred_at=record.published_at or candidate.created_at,
                title=record.title,
                summary=f"公告候选状态：{candidate.status}",
                source_label=record.source_code,
                target_url=f"/information/announcements/{candidate.id}",
                confidence=None,
                data_completeness=record.data_completeness,
                created_by="system_rule",
            )
        )
    information_rows = list(
        (
            await session.execute(
                select(InformationItem)
                .join(InformationStockRelation, InformationStockRelation.information_item_id == InformationItem.id)
                .where(
                    InformationItem.user_id == user_id,
                    InformationItem.archived_at.is_(None),
                    InformationStockRelation.stock_id == stock_id,
                    InformationStockRelation.relation_status == "confirmed",
                )
                .order_by(InformationItem.created_at.desc())
                .limit(30)
            )
        )
        .scalars()
        .all()
    )
    for item in information_rows:
        entries.append(
            TimelineEntryOut(
                event_type="information_item",
                occurred_at=item.created_at,
                title=item.title or "未命名信息",
                summary=f"信息状态：{item.status}",
                source_label=item.source_type,
                target_url=f"/information/items/{item.id}",
                confidence=None,
                data_completeness=None,
                created_by="user",
            )
        )
    analysis_rows = list(
        (
            await session.execute(
                select(InformationAnalysisVersion, InformationItem)
                .join(InformationItem, InformationItem.id == InformationAnalysisVersion.information_item_id)
                .join(InformationStockRelation, InformationStockRelation.information_item_id == InformationItem.id)
                .where(
                    InformationItem.user_id == user_id,
                    InformationStockRelation.stock_id == stock_id,
                    InformationStockRelation.relation_status == "confirmed",
                )
                .order_by(InformationAnalysisVersion.created_at.desc())
                .limit(20)
            )
        ).all()
    )
    for analysis, item in analysis_rows:
        entries.append(
            TimelineEntryOut(
                event_type="ai_analysis_version",
                occurred_at=analysis.created_at,
                title=f"AI结构化分析 v{analysis.version_number}",
                summary=_analysis_summary(analysis.structured_result),
                source_label=item.title or item.source_type,
                target_url=f"/information/items/{item.id}",
                confidence=analysis.analysis_status,
                data_completeness=None,
                created_by="ai_gateway",
            )
        )
    for task in tasks:
        entries.append(
            TimelineEntryOut(
                event_type="research_task.created",
                occurred_at=task.created_at,
                title=task.title,
                summary=f"{task.task_type} / {task.status}",
                source_label=task.source_type,
                target_url=f"/information/tasks?task={task.id}",
                confidence=task.priority,
                data_completeness=None,
                created_by=task.created_by,
            )
        )
        for update in task.updates:
            entries.append(_task_update_entry(task, update))
    review_rows = await _review_history(session, user_id=user_id, stock_id=stock_id)
    for review in review_rows:
        entries.append(
            TimelineEntryOut(
                event_type="daily_review_version",
                occurred_at=datetime.combine(review.review_date, time.min, tzinfo=UTC),
                title=f"{review.review_date.isoformat()} 复盘",
                summary=f"状态 {review.status}，版本 {review.version_count} 个",
                source_label="daily_review",
                target_url=review.target_url,
                confidence=None,
                data_completeness=None,
                created_by="system_rule",
            )
        )
    entries.sort(key=lambda entry: (entry.occurred_at, entry.event_type, entry.title), reverse=True)
    return entries[:80]


def _task_update_entry(task: ResearchTask, update: ResearchTaskUpdate) -> TimelineEntryOut:
    return TimelineEntryOut(
        event_type="research_task.status_changed" if update.previous_status != update.new_status else "research_task.update",
        occurred_at=update.created_at,
        title=task.title,
        summary=f"{update.previous_status or '无'} -> {update.new_status}；{update.note or '无备注'}",
        source_label="research_task",
        target_url=f"/information/tasks?task={task.id}",
        confidence=task.priority,
        data_completeness=None,
        created_by=update.created_by,
    )


async def _review_history(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    stock_id: uuid.UUID,
) -> list[ReviewHistoryOut]:
    rows = list(
        (
            await session.execute(
                select(DailyReview, func.count(DailyReviewVersion.id), func.max(DailyReviewVersion.version_number))
                .join(DailyReviewVersion, DailyReviewVersion.daily_review_id == DailyReview.id)
                .where(DailyReview.user_id == user_id, DailyReview.archived_at.is_(None))
                .group_by(DailyReview.id)
                .order_by(DailyReview.review_date.desc())
                .limit(20)
            )
        ).all()
    )
    result: list[ReviewHistoryOut] = []
    for review, version_count, latest_version in rows:
        if not await _review_mentions_stock(session, review.id, stock_id):
            continue
        result.append(
            ReviewHistoryOut(
                review_id=review.id,
                review_date=review.review_date,
                status=review.status,
                stale=review.status == "stale",
                version_count=int(version_count),
                latest_version=int(latest_version) if latest_version else None,
                target_url=f"/reviews/{review.id}",
            )
        )
    return result


async def _review_mentions_stock(session: AsyncSession, review_id: uuid.UUID, stock_id: uuid.UUID) -> bool:
    versions = list(
        (
            await session.execute(
                select(DailyReviewVersion)
                .where(DailyReviewVersion.daily_review_id == review_id)
                .order_by(DailyReviewVersion.version_number.desc())
                .limit(3)
            )
        )
        .scalars()
        .all()
    )
    needle = str(stock_id)
    return any(needle in str(version.rule_snapshot) or needle in str(version.ai_structured_result or {}) for version in versions)


def _analysis_summary(value: dict[str, Any]) -> str:
    summary = value.get("summary")
    if isinstance(summary, str) and summary:
        return summary[:240]
    facts = value.get("facts")
    if isinstance(facts, list):
        return f"结构化事实 {len(facts)} 条"
    return "结构化分析已保存"


def _market_summary(rows: list) -> dict[str, Any]:
    rows_with_snapshot = [row for row in rows if row.snapshot is not None]
    unavailable_count = len(rows) - len(rows_with_snapshot)
    pct_values = [row.snapshot.pct_change for row in rows_with_snapshot if row.snapshot and row.snapshot.pct_change is not None]
    trade_dates = [row.snapshot.trade_date for row in rows_with_snapshot if row.snapshot]
    partial_or_stale_count = sum(1 for row in rows_with_snapshot if row.status in {"partial", "stale", "source_lag"})
    return {
        "market_trade_date": max(trade_dates) if trade_dates else None,
        "market_snapshot_count": len(rows_with_snapshot),
        "market_data_available_count": len(rows_with_snapshot),
        "market_data_unavailable_count": unavailable_count,
        "gainers_count": sum(1 for value in pct_values if value > 0),
        "decliners_count": sum(1 for value in pct_values if value < 0),
        "unchanged_count": sum(1 for value in pct_values if value == 0),
        "partial_or_stale_count": partial_or_stale_count,
    }


def _market_data_status(summary: dict[str, Any], latest_trade_date: date | None) -> str:
    if not latest_trade_date or summary["market_snapshot_count"] == 0:
        return "unavailable"
    if summary["market_data_unavailable_count"] > 0 or summary["partial_or_stale_count"] > 0:
        return "partial"
    return "available"


def _market_quote_fields(row) -> dict[str, Any]:
    snapshot = row.snapshot if row else None
    if snapshot is None:
        return {
            "close": None,
            "pct_change": None,
            "amount": None,
            "turnover_rate": None,
            "trade_date": None,
            "source_code": None,
            "freshness_status": row.status if row else "unavailable",
            "change": None,
            "volume": None,
        }
    return {
        "close": snapshot.close,
        "pct_change": snapshot.pct_change,
        "amount": snapshot.amount,
        "turnover_rate": snapshot.turnover_rate,
        "trade_date": snapshot.trade_date,
        "source_code": snapshot.source_code,
        "freshness_status": row.status,
        "change": snapshot.change,
        "volume": snapshot.volume,
    }


def _business_today(settings: Settings) -> date:
    return datetime.now(UTC).astimezone(ZoneInfo(settings.app_timezone)).date()


def _date_window(date_from: date, date_to: date, timezone_name: str) -> tuple[datetime, datetime]:
    tz = ZoneInfo(timezone_name)
    start = datetime.combine(date_from, time.min, tzinfo=tz).astimezone(UTC)
    end = (datetime.combine(date_to, time.min, tzinfo=tz) + timedelta(days=1)).astimezone(UTC)
    return start, end
