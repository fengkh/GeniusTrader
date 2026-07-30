import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.core.time import utc_now
from app.models.review_notification import (
    BusinessEvent,
    Notification,
    NotificationDelivery,
    NotificationPreference,
)
from app.schemas.notification import NotificationPatch, NotificationPreferenceUpdateItem
from app.services.audit import add_audit_log, sanitize_metadata

SUPPORTED_EVENT_TYPES = [
    "user_daily_review.generated",
    "user_daily_review.partial",
    "user_daily_review.failed",
    "user_daily_review.became_stale",
    "information.high_priority_detected",
    "information.verification_required",
    "ai_task.failed",
    "research_task.created",
    "research_task.status_changed",
    "research_task.due",
    "observation_condition.due",
]

SEVERITY_RANK = {"info": 0, "notice": 1, "important": 2}

DEFAULT_PREFERENCES = {
    "user_daily_review.generated": {"enabled": True, "frequency": "immediate", "minimum_severity": "info"},
    "user_daily_review.partial": {"enabled": True, "frequency": "immediate", "minimum_severity": "notice"},
    "user_daily_review.failed": {"enabled": True, "frequency": "immediate", "minimum_severity": "important"},
    "user_daily_review.became_stale": {"enabled": True, "frequency": "immediate", "minimum_severity": "notice"},
    "information.high_priority_detected": {"enabled": True, "frequency": "immediate", "minimum_severity": "notice"},
    "information.verification_required": {"enabled": True, "frequency": "daily_digest", "minimum_severity": "notice"},
    "ai_task.failed": {"enabled": True, "frequency": "immediate", "minimum_severity": "notice"},
    "research_task.created": {"enabled": True, "frequency": "daily_digest", "minimum_severity": "info"},
    "research_task.status_changed": {"enabled": True, "frequency": "daily_digest", "minimum_severity": "info"},
    "research_task.due": {"enabled": True, "frequency": "daily_digest", "minimum_severity": "notice"},
    "observation_condition.due": {"enabled": True, "frequency": "immediate", "minimum_severity": "notice"},
}


def ensure_supported_event_type(event_type: str) -> None:
    if event_type not in SUPPORTED_EVENT_TYPES:
        raise AppError(ErrorCode.EVENT_TYPE_NOT_SUPPORTED, "不支持的事件类型", status_code=422)


def _safe_summary(value: str, max_length: int = 220) -> str:
    text = " ".join(value.split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1]}…"


def _event_title(event: BusinessEvent) -> str:
    titles = {
        "user_daily_review.generated": "每日复盘已生成",
        "user_daily_review.partial": "每日复盘部分完成",
        "user_daily_review.failed": "每日复盘生成失败",
        "user_daily_review.became_stale": "复盘需要更新",
        "information.high_priority_detected": "重要信息已标记",
        "information.verification_required": "存在待核实事项",
        "ai_task.failed": "AI 分析失败",
        "research_task.created": "研究事项已创建",
        "research_task.status_changed": "研究事项状态已更新",
        "research_task.due": "研究事项到期",
        "observation_condition.due": "观察条件到期",
    }
    return titles.get(event.event_type, event.event_type)


def _event_summary(event: BusinessEvent) -> str:
    payload = event.payload or {}
    if event.event_type.startswith("user_daily_review."):
        review_date = payload.get("review_date", "")
        status = payload.get("status", event.severity)
        total = payload.get("total_information_count", 0)
        verification = payload.get("verification_item_count", 0)
        return _safe_summary(f"{review_date} 用户私有信息复盘状态为 {status}，纳入信息 {total} 条，待核实 {verification} 项。")
    if event.event_type == "information.high_priority_detected":
        return _safe_summary(f"用户标记了一条与自选股相关的重要信息：{payload.get('title', '未命名信息')}")
    if event.event_type == "information.verification_required":
        return _safe_summary(f"信息分析发现待核实事项 {payload.get('verification_item_count', 0)} 项，将进入每日复盘。")
    if event.event_type == "ai_task.failed":
        return _safe_summary(f"AI 分析最终失败，错误码：{payload.get('error_code', 'unknown')}。确定性数据仍保留。")
    if event.event_type in {"research_task.created", "research_task.status_changed"}:
        return _safe_summary(f"研究事项：{payload.get('title') or payload.get('task_id', '')}")
    if event.event_type in {"research_task.due", "observation_condition.due"}:
        due_date = payload.get("due_date", "")
        return _safe_summary(f"{due_date} 到期：{payload.get('title', '未命名研究事项')}")
    return _safe_summary(event.event_type)


def _target_for_event(event: BusinessEvent) -> tuple[str, uuid.UUID, str]:
    if event.subject_type == "daily_review":
        return "daily_review", event.subject_id, f"/reviews/{event.subject_id}"
    if event.subject_type == "information_item":
        return "information_item", event.subject_id, f"/information/{event.subject_id}"
    if event.subject_type == "research_task":
        return "research_task", event.subject_id, f"/information/tasks?task={event.subject_id}"
    return event.subject_type, event.subject_id, "/notifications"


async def ensure_notification_preferences(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[NotificationPreference]:
    existing = list(
        (
            await session.execute(
                select(NotificationPreference).where(
                    NotificationPreference.user_id == user_id,
                    NotificationPreference.channel == "in_app",
                )
            )
        )
        .scalars()
        .all()
    )
    by_event = {preference.event_type: preference for preference in existing}
    for event_type in SUPPORTED_EVENT_TYPES:
        if event_type in by_event:
            continue
        defaults = DEFAULT_PREFERENCES[event_type]
        preference = NotificationPreference(
            user_id=user_id,
            event_type=event_type,
            channel="in_app",
            enabled=defaults["enabled"],
            frequency=defaults["frequency"],
            minimum_severity=defaults["minimum_severity"],
            quiet_hours_start=None,
            quiet_hours_end=None,
            timezone="Asia/Shanghai",
        )
        session.add(preference)
        by_event[event_type] = preference
    await session.flush()
    return [by_event[event_type] for event_type in SUPPORTED_EVENT_TYPES]


async def update_notification_preferences(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    items: list[NotificationPreferenceUpdateItem],
    request_id: str | None,
) -> list[NotificationPreference]:
    preferences = await ensure_notification_preferences(session, user_id=user_id)
    by_event = {preference.event_type: preference for preference in preferences}
    seen: set[str] = set()
    for item in items:
        ensure_supported_event_type(item.event_type)
        if item.event_type in seen:
            raise AppError(ErrorCode.NOTIFICATION_PREFERENCE_INVALID, "通知偏好事件类型重复", status_code=422)
        seen.add(item.event_type)
        preference = by_event[item.event_type]
        preference.enabled = item.enabled
        preference.frequency = item.frequency
        preference.minimum_severity = item.minimum_severity
        preference.quiet_hours_start = item.quiet_hours_start
        preference.quiet_hours_end = item.quiet_hours_end
        preference.timezone = item.timezone
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="notification_preferences.update",
        target_type="notification_preferences",
        target_id=None,
        result="success",
        request_id=request_id,
        metadata={"updated_event_types": sorted(seen), "channel": "in_app"},
    )
    await session.commit()
    return await ensure_notification_preferences(session, user_id=user_id)


async def create_business_event(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    event_type: str,
    subject_type: str,
    subject_id: uuid.UUID,
    severity: str,
    payload: dict[str, Any],
    source: str,
    idempotency_key: str,
    request_id: str | None,
    correlation_id: str | None = None,
    notify: bool = True,
) -> tuple[BusinessEvent, Notification | None]:
    ensure_supported_event_type(event_type)
    if severity not in SEVERITY_RANK:
        raise AppError(ErrorCode.VALIDATION_ERROR, "事件严重程度无效", status_code=422)
    existing = (
        await session.execute(
            select(BusinessEvent).where(
                BusinessEvent.user_id == user_id,
                BusinessEvent.idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing, None
    now = utc_now()
    event = BusinessEvent(
        user_id=user_id,
        event_type=event_type,
        event_version="v1",
        occurred_at=now,
        subject_type=subject_type,
        subject_id=subject_id,
        severity=severity,
        payload=sanitize_metadata(payload),
        source=source,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        created_at=now,
    )
    session.add(event)
    await session.flush()
    notification = await orchestrate_notification(session, event=event) if notify else None
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="business_event.create",
        target_type="business_event",
        target_id=event.id,
        result="success",
        request_id=request_id,
        metadata={"event_type": event_type, "severity": severity},
    )
    return event, notification


async def orchestrate_notification(
    session: AsyncSession,
    *,
    event: BusinessEvent,
) -> Notification | None:
    preferences = await ensure_notification_preferences(session, user_id=event.user_id)
    preference = next((item for item in preferences if item.event_type == event.event_type), None)
    if not preference or not preference.enabled or preference.frequency in {"disabled", "daily_digest"}:
        return None
    if SEVERITY_RANK[event.severity] < SEVERITY_RANK[preference.minimum_severity]:
        return None
    existing = (
        await session.execute(
            select(Notification).where(Notification.user_id == event.user_id, Notification.event_id == event.id)
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    target_type, target_id, deep_link = _target_for_event(event)
    notification = Notification(
        user_id=event.user_id,
        event_id=event.id,
        event_type=event.event_type,
        title=_event_title(event),
        summary=_event_summary(event),
        severity=event.severity,
        target_type=target_type,
        target_id=target_id,
        deep_link=deep_link,
        status="unread",
    )
    session.add(notification)
    await session.flush()
    now = utc_now()
    session.add(
        NotificationDelivery(
            notification_id=notification.id,
            user_id=event.user_id,
            channel="in_app",
            status="delivered",
            attempt_count=1,
            queued_at=now,
            delivered_at=now,
            deduplication_key=f"in_app:{notification.id}",
        )
    )
    return notification


def _apply_notification_filters(
    statement: Select[tuple[Notification]],
    *,
    user_id: uuid.UUID,
    status: str | None,
    event_type: str | None,
) -> Select[tuple[Notification]]:
    statement = statement.where(Notification.user_id == user_id)
    if status:
        statement = statement.where(Notification.status == status)
    else:
        statement = statement.where(Notification.status != "archived")
    if event_type:
        ensure_supported_event_type(event_type)
        statement = statement.where(Notification.event_type == event_type)
    return statement


async def list_notifications(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    status: str | None,
    event_type: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Notification], int]:
    base = _apply_notification_filters(select(Notification), user_id=user_id, status=status, event_type=event_type)
    total = (await session.execute(select(func.count()).select_from(base.order_by(None).subquery()))).scalar_one()
    rows = list(
        (
            await session.execute(base.order_by(Notification.created_at.desc()).limit(limit).offset(offset))
        )
        .scalars()
        .all()
    )
    return rows, total


async def get_notification_or_404(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    notification_id: uuid.UUID,
) -> Notification:
    notification = (
        await session.execute(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not notification:
        raise AppError(ErrorCode.NOTIFICATION_NOT_FOUND, "通知不存在", status_code=404)
    return notification


async def unread_count(session: AsyncSession, *, user_id: uuid.UUID) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.status == "unread")
        )
    ).scalar_one()


def apply_notification_action(notification: Notification, action: str, now: datetime) -> None:
    if action == "mark_read":
        notification.status = "read"
        notification.read_at = notification.read_at or now
        notification.archived_at = None
    elif action == "mark_unread":
        notification.status = "unread"
        notification.read_at = None
        notification.archived_at = None
    elif action == "archive":
        notification.status = "archived"
        notification.archived_at = notification.archived_at or now
    elif action == "unarchive":
        notification.status = "read" if notification.read_at else "unread"
        notification.archived_at = None


async def patch_notification(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    notification_id: uuid.UUID,
    payload: NotificationPatch,
    request_id: str | None,
) -> Notification:
    notification = await get_notification_or_404(session, user_id=user_id, notification_id=notification_id)
    apply_notification_action(notification, payload.action, utc_now())
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action=f"notification.{payload.action}",
        target_type="notification",
        target_id=notification.id,
        result="success",
        request_id=request_id,
    )
    await session.commit()
    await session.refresh(notification)
    return notification


async def mark_all_read(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    event_type: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    request_id: str | None,
) -> int:
    if event_type:
        ensure_supported_event_type(event_type)
    statement = select(Notification).where(Notification.user_id == user_id, Notification.status == "unread")
    if event_type:
        statement = statement.where(Notification.event_type == event_type)
    if date_from:
        statement = statement.where(Notification.created_at >= date_from)
    if date_to:
        statement = statement.where(Notification.created_at <= date_to)
    notifications = list((await session.execute(statement)).scalars().all())
    now = utc_now()
    for notification in notifications:
        notification.status = "read"
        notification.read_at = notification.read_at or now
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="notification.mark_all_read",
        target_type="notification",
        target_id=None,
        result="success",
        request_id=request_id,
        metadata={"count": len(notifications), "event_type": event_type},
    )
    await session.commit()
    return len(notifications)
