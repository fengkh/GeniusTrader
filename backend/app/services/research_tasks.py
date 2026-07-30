import uuid
from datetime import date

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError, ErrorCode
from app.core.time import utc_now
from app.models.information import InformationAnalysisVersion, InformationItem
from app.models.research import ResearchTask, ResearchTaskUpdate
from app.models.review_notification import DailyReview, DailyReviewVersion
from app.models.stock import Stock
from app.schemas.common import Page
from app.schemas.research import (
    ResearchTaskCreate,
    ResearchTaskOut,
    ResearchTaskPatch,
    ResearchTaskStatusUpdate,
    ResearchTaskUpdateCreate,
)
from app.services.audit import add_audit_log
from app.services.notifications import create_business_event

OPEN_RESEARCH_TASK_STATUSES = ("pending", "monitoring")
RESOLVED_RESEARCH_TASK_STATUSES = (
    "confirmed",
    "disproved",
    "partially_confirmed",
    "unable_to_determine",
    "no_longer_applicable",
    "dismissed",
)


def is_open_research_status(status: str) -> bool:
    return status in OPEN_RESEARCH_TASK_STATUSES


async def list_research_tasks(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    task_type: str | None,
    status: str | None,
    priority: str | None,
    stock_id: uuid.UUID | None,
    due_date: date | None,
    source_type: str | None,
    keyword: str | None,
    open_only: bool,
    limit: int,
    offset: int,
) -> Page[ResearchTaskOut]:
    statement = _base_task_query(user_id)
    statement = _apply_task_filters(
        statement,
        task_type=task_type,
        status=status,
        priority=priority,
        stock_id=stock_id,
        due_date=due_date,
        source_type=source_type,
        keyword=keyword,
        open_only=open_only,
    )
    total = (await session.execute(select(func.count()).select_from(statement.order_by(None).subquery()))).scalar_one()
    rows = list(
        (
            await session.execute(
                statement.order_by(ResearchTask.updated_at.desc(), ResearchTask.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .unique()
        .all()
    )
    return Page(
        items=[ResearchTaskOut.model_validate(row) for row in rows],
        limit=limit,
        offset=offset,
        total=total,
    )


async def get_research_task_or_404(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
) -> ResearchTask:
    task = (
        await session.execute(
            _base_task_query(user_id)
            .where(ResearchTask.id == task_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if not task:
        raise AppError(ErrorCode.RESEARCH_TASK_NOT_FOUND, "研究事项不存在", status_code=404)
    return task


async def create_research_task(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    payload: ResearchTaskCreate,
    request_id: str | None,
) -> ResearchTaskOut:
    await _validate_research_task_references(session, user_id=user_id, payload=payload)
    deduplication_key = _deduplication_key(payload)
    if deduplication_key:
        existing = await _get_task_by_deduplication_key(session, user_id=user_id, key=deduplication_key)
        if existing:
            return ResearchTaskOut.model_validate(existing)
    now = utc_now()
    task = ResearchTask(
        user_id=user_id,
        stock_id=payload.stock_id,
        task_type=payload.task_type,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
        source_type=payload.source_type,
        source_information_item_id=payload.source_information_item_id,
        source_analysis_version_id=payload.source_analysis_version_id,
        source_daily_review_id=payload.source_daily_review_id,
        source_daily_review_version_id=payload.source_daily_review_version_id,
        due_date=payload.due_date,
        current_evidence_summary=payload.current_evidence_summary,
        created_by="user",
        deduplication_key=deduplication_key,
        resolved_at=now if not is_open_research_status(payload.status) else None,
    )
    session.add(task)
    try:
        await session.flush()
    except IntegrityError as exc:
        if deduplication_key:
            await session.rollback()
            existing = await _get_task_by_deduplication_key(session, user_id=user_id, key=deduplication_key)
            if existing:
                return ResearchTaskOut.model_validate(existing)
        raise AppError(ErrorCode.VALIDATION_ERROR, "研究事项创建失败", status_code=409) from exc
    session.add(
        ResearchTaskUpdate(
            task_id=task.id,
            user_id=user_id,
            previous_status=None,
            new_status=task.status,
            note="创建研究事项",
            created_by="user",
            created_at=now,
        )
    )
    await create_business_event(
        session,
        user_id=user_id,
        event_type="research_task.created",
        subject_type="research_task",
        subject_id=task.id,
        severity="info",
        payload={"task_id": str(task.id), "task_type": task.task_type, "title": _safe_text(task.title, 120)},
        source="research_task_service",
        idempotency_key=f"research_task.created:{task.id}",
        request_id=request_id,
        notify=False,
        correlation_id=request_id,
    )
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="research_task.create",
        target_type="research_task",
        target_id=task.id,
        result="success",
        request_id=request_id,
        metadata={"task_type": task.task_type, "source_type": task.source_type},
    )
    await session.commit()
    return ResearchTaskOut.model_validate(await get_research_task_or_404(session, user_id=user_id, task_id=task.id))


async def patch_research_task(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: ResearchTaskPatch,
    request_id: str | None,
) -> ResearchTaskOut:
    task = await get_research_task_or_404(session, user_id=user_id, task_id=task_id)
    if payload.stock_id is not None:
        await _ensure_stock_exists(session, payload.stock_id)
        task.stock_id = payload.stock_id
    for field in ("title", "description", "priority", "due_date", "current_evidence_summary", "resolution_note"):
        value = getattr(payload, field)
        if value is not None:
            setattr(task, field, value)
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="research_task.update",
        target_type="research_task",
        target_id=task.id,
        result="success",
        request_id=request_id,
    )
    await session.commit()
    return ResearchTaskOut.model_validate(await get_research_task_or_404(session, user_id=user_id, task_id=task.id))


async def update_research_task_status(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: ResearchTaskStatusUpdate,
    request_id: str | None,
) -> ResearchTaskOut:
    task = await get_research_task_or_404(session, user_id=user_id, task_id=task_id)
    await _validate_evidence_references(
        session,
        user_id=user_id,
        evidence_information_item_id=payload.evidence_information_item_id,
        evidence_analysis_version_id=payload.evidence_analysis_version_id,
        evidence_daily_review_version_id=payload.evidence_daily_review_version_id,
    )
    previous_status = task.status
    now = utc_now()
    task.status = payload.status
    if payload.status in RESOLVED_RESEARCH_TASK_STATUSES:
        task.resolved_at = task.resolved_at or now
        if payload.note:
            task.resolution_note = payload.note
    elif payload.status in OPEN_RESEARCH_TASK_STATUSES:
        task.resolved_at = None
    session.add(
        ResearchTaskUpdate(
            task_id=task.id,
            user_id=user_id,
            previous_status=previous_status,
            new_status=payload.status,
            note=payload.note,
            evidence_information_item_id=payload.evidence_information_item_id,
            evidence_analysis_version_id=payload.evidence_analysis_version_id,
            evidence_daily_review_version_id=payload.evidence_daily_review_version_id,
            created_by="user",
            created_at=now,
        )
    )
    await create_business_event(
        session,
        user_id=user_id,
        event_type="research_task.status_changed",
        subject_type="research_task",
        subject_id=task.id,
        severity="info",
        payload={"task_id": str(task.id), "previous_status": previous_status, "new_status": payload.status},
        source="research_task_service",
        idempotency_key=f"research_task.status_changed:{task.id}:{now.isoformat()}",
        request_id=request_id,
        notify=False,
        correlation_id=request_id,
    )
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="research_task.status",
        target_type="research_task",
        target_id=task.id,
        result="success",
        request_id=request_id,
        metadata={"previous_status": previous_status, "new_status": payload.status},
    )
    await session.commit()
    return ResearchTaskOut.model_validate(await get_research_task_or_404(session, user_id=user_id, task_id=task.id))


async def add_research_task_update(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: ResearchTaskUpdateCreate,
    request_id: str | None,
) -> ResearchTaskOut:
    task = await get_research_task_or_404(session, user_id=user_id, task_id=task_id)
    await _validate_evidence_references(
        session,
        user_id=user_id,
        evidence_information_item_id=payload.evidence_information_item_id,
        evidence_analysis_version_id=payload.evidence_analysis_version_id,
        evidence_daily_review_version_id=payload.evidence_daily_review_version_id,
    )
    session.add(
        ResearchTaskUpdate(
            task_id=task.id,
            user_id=user_id,
            previous_status=task.status,
            new_status=task.status,
            note=payload.note,
            evidence_information_item_id=payload.evidence_information_item_id,
            evidence_analysis_version_id=payload.evidence_analysis_version_id,
            evidence_daily_review_version_id=payload.evidence_daily_review_version_id,
            created_by="user",
            created_at=utc_now(),
        )
    )
    if payload.note:
        task.current_evidence_summary = _safe_text(payload.note, 1000)
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="research_task_update.create",
        target_type="research_task",
        target_id=task.id,
        result="success",
        request_id=request_id,
    )
    await session.commit()
    return ResearchTaskOut.model_validate(await get_research_task_or_404(session, user_id=user_id, task_id=task.id))


async def dismiss_research_task(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    request_id: str | None,
) -> None:
    await update_research_task_status(
        session,
        user_id=user_id,
        task_id=task_id,
        payload=ResearchTaskStatusUpdate(status="dismissed", note="用户忽略该事项"),
        request_id=request_id,
    )


async def create_due_research_task_events(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    business_date: date,
    request_id: str | None,
) -> None:
    tasks = list(
        (
            await session.execute(
                select(ResearchTask).where(
                    ResearchTask.user_id == user_id,
                    ResearchTask.status.in_(OPEN_RESEARCH_TASK_STATUSES),
                    ResearchTask.due_date.is_not(None),
                    ResearchTask.due_date <= business_date,
                )
            )
        )
        .scalars()
        .all()
    )
    for task in tasks:
        event_type = "observation_condition.due" if task.task_type == "observation" else "research_task.due"
        await create_business_event(
            session,
            user_id=user_id,
            event_type=event_type,
            subject_type="research_task",
            subject_id=task.id,
            severity="notice" if task.priority != "high" else "important",
            payload={
                "task_id": str(task.id),
                "task_type": task.task_type,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "title": _safe_text(task.title, 120),
            },
            source="today_overview",
            idempotency_key=f"{event_type}:{task.id}:{business_date.isoformat()}",
            request_id=request_id,
            correlation_id=request_id,
        )


def _base_task_query(user_id: uuid.UUID) -> Select[tuple[ResearchTask]]:
    return (
        select(ResearchTask)
        .options(selectinload(ResearchTask.stock), selectinload(ResearchTask.updates))
        .where(ResearchTask.user_id == user_id)
    )


def _apply_task_filters(
    statement: Select[tuple[ResearchTask]],
    *,
    task_type: str | None,
    status: str | None,
    priority: str | None,
    stock_id: uuid.UUID | None,
    due_date: date | None,
    source_type: str | None,
    keyword: str | None,
    open_only: bool,
) -> Select[tuple[ResearchTask]]:
    if task_type:
        statement = statement.where(ResearchTask.task_type == task_type)
    if status:
        statement = statement.where(ResearchTask.status == status)
    if priority:
        statement = statement.where(ResearchTask.priority == priority)
    if stock_id:
        statement = statement.where(ResearchTask.stock_id == stock_id)
    if due_date:
        statement = statement.where(ResearchTask.due_date == due_date)
    if source_type:
        statement = statement.where(ResearchTask.source_type == source_type)
    if open_only:
        statement = statement.where(ResearchTask.status.in_(OPEN_RESEARCH_TASK_STATUSES))
    if keyword:
        like = f"%{keyword.strip()}%"
        statement = statement.where(or_(ResearchTask.title.ilike(like), ResearchTask.description.ilike(like)))
    return statement


async def _validate_research_task_references(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    payload: ResearchTaskCreate,
) -> None:
    if payload.stock_id:
        await _ensure_stock_exists(session, payload.stock_id)
    if payload.source_information_item_id:
        await _ensure_information_owner(session, user_id=user_id, item_id=payload.source_information_item_id)
    if payload.source_analysis_version_id:
        await _ensure_analysis_owner(
            session,
            user_id=user_id,
            analysis_version_id=payload.source_analysis_version_id,
            expected_item_id=payload.source_information_item_id,
        )
    if payload.source_daily_review_id:
        await _ensure_daily_review_owner(session, user_id=user_id, review_id=payload.source_daily_review_id)
    if payload.source_daily_review_version_id:
        await _ensure_daily_review_version_owner(
            session,
            user_id=user_id,
            version_id=payload.source_daily_review_version_id,
            expected_review_id=payload.source_daily_review_id,
        )


async def _validate_evidence_references(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    evidence_information_item_id: uuid.UUID | None,
    evidence_analysis_version_id: uuid.UUID | None,
    evidence_daily_review_version_id: uuid.UUID | None,
) -> None:
    if evidence_information_item_id:
        await _ensure_information_owner(session, user_id=user_id, item_id=evidence_information_item_id)
    if evidence_analysis_version_id:
        await _ensure_analysis_owner(
            session,
            user_id=user_id,
            analysis_version_id=evidence_analysis_version_id,
            expected_item_id=evidence_information_item_id,
        )
    if evidence_daily_review_version_id:
        await _ensure_daily_review_version_owner(
            session,
            user_id=user_id,
            version_id=evidence_daily_review_version_id,
            expected_review_id=None,
        )


async def _ensure_stock_exists(session: AsyncSession, stock_id: uuid.UUID) -> Stock:
    stock = await session.get(Stock, stock_id)
    if not stock:
        raise AppError(ErrorCode.STOCK_NOT_FOUND, "股票不存在", status_code=404)
    return stock


async def _ensure_information_owner(session: AsyncSession, *, user_id: uuid.UUID, item_id: uuid.UUID) -> InformationItem:
    item = (
        await session.execute(select(InformationItem).where(InformationItem.id == item_id, InformationItem.user_id == user_id))
    ).scalar_one_or_none()
    if not item:
        raise AppError(ErrorCode.INFORMATION_NOT_FOUND, "信息条目不存在", status_code=404)
    return item


async def _ensure_analysis_owner(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    analysis_version_id: uuid.UUID,
    expected_item_id: uuid.UUID | None,
) -> InformationAnalysisVersion:
    analysis = (
        await session.execute(
            select(InformationAnalysisVersion, InformationItem)
            .join(InformationItem, InformationItem.id == InformationAnalysisVersion.information_item_id)
            .where(InformationAnalysisVersion.id == analysis_version_id, InformationItem.user_id == user_id)
        )
    ).one_or_none()
    if not analysis:
        raise AppError(ErrorCode.INFORMATION_NOT_FOUND, "分析版本不存在", status_code=404)
    version, item = analysis
    if expected_item_id and item.id != expected_item_id:
        raise AppError(ErrorCode.VALIDATION_ERROR, "分析版本与来源信息不匹配", status_code=422)
    return version


async def _ensure_daily_review_owner(session: AsyncSession, *, user_id: uuid.UUID, review_id: uuid.UUID) -> DailyReview:
    review = (
        await session.execute(select(DailyReview).where(DailyReview.id == review_id, DailyReview.user_id == user_id))
    ).scalar_one_or_none()
    if not review:
        raise AppError(ErrorCode.DAILY_REVIEW_NOT_FOUND, "复盘不存在", status_code=404)
    return review


async def _ensure_daily_review_version_owner(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    version_id: uuid.UUID,
    expected_review_id: uuid.UUID | None,
) -> DailyReviewVersion:
    row = (
        await session.execute(
            select(DailyReviewVersion, DailyReview)
            .join(DailyReview, DailyReview.id == DailyReviewVersion.daily_review_id)
            .where(DailyReviewVersion.id == version_id, DailyReview.user_id == user_id)
        )
    ).one_or_none()
    if not row:
        raise AppError(ErrorCode.DAILY_REVIEW_VERSION_NOT_FOUND, "复盘版本不存在", status_code=404)
    version, review = row
    if expected_review_id and review.id != expected_review_id:
        raise AppError(ErrorCode.VALIDATION_ERROR, "复盘版本与来源复盘不匹配", status_code=422)
    return version


def _deduplication_key(payload: ResearchTaskCreate) -> str | None:
    if not payload.suggestion_identifier:
        return None
    anchor = (
        payload.source_analysis_version_id
        or payload.source_daily_review_version_id
        or payload.source_information_item_id
        or payload.source_daily_review_id
    )
    if not anchor:
        return None
    return f"{payload.source_type}:{anchor}:{payload.task_type}:{payload.suggestion_identifier}"


async def _get_task_by_deduplication_key(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    key: str,
) -> ResearchTask | None:
    return (
        await session.execute(
            _base_task_query(user_id).where(ResearchTask.deduplication_key == key)
        )
    ).scalar_one_or_none()


def _safe_text(value: str | None, max_length: int = 240) -> str:
    if not value:
        return ""
    text = " ".join(value.split())
    return text if len(text) <= max_length else f"{text[: max_length - 1]}…"
