from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.dependencies import CurrentUser, SessionDependency, get_request_id
from app.schemas.common import DataEnvelope, MessageResponse, Page
from app.schemas.notification import (
    NotificationMarkAllReadRequest,
    NotificationOut,
    NotificationPatch,
    NotificationPreferenceOut,
    NotificationPreferenceUpdateRequest,
    NotificationUnreadCountOut,
)
from app.services.notifications import (
    ensure_notification_preferences,
    get_notification_or_404,
    list_notifications,
    mark_all_read,
    patch_notification,
    unread_count,
    update_notification_preferences,
)

router = APIRouter()
preferences_router = APIRouter()


@router.get("", response_model=DataEnvelope[Page[NotificationOut]])
async def get_notifications(
    session: SessionDependency,
    current_user: CurrentUser,
    status_value: Annotated[str | None, Query(alias="status", max_length=32)] = None,
    event_type: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Page[NotificationOut]]:
    items, total = await list_notifications(
        session,
        user_id=current_user.id,
        status=status_value,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    return {
        "data": Page(
            items=[NotificationOut.model_validate(item) for item in items],
            limit=limit,
            offset=offset,
            total=total,
        )
    }


@router.get("/unread-count", response_model=DataEnvelope[NotificationUnreadCountOut])
async def get_unread_count(
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, NotificationUnreadCountOut]:
    return {"data": NotificationUnreadCountOut(unread_count=await unread_count(session, user_id=current_user.id))}


@router.post("/mark-all-read", response_model=DataEnvelope[MessageResponse])
async def mark_all_read_route(
    payload: NotificationMarkAllReadRequest,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, MessageResponse]:
    count = await mark_all_read(
        session,
        user_id=current_user.id,
        event_type=payload.event_type,
        date_from=payload.date_from,
        date_to=payload.date_to,
        request_id=get_request_id(request),
    )
    return {"data": MessageResponse(message=f"marked {count} notifications as read")}


@router.get("/{notification_id}", response_model=DataEnvelope[NotificationOut])
async def get_notification(
    notification_id: UUID,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, NotificationOut]:
    return {
        "data": NotificationOut.model_validate(
            await get_notification_or_404(session, user_id=current_user.id, notification_id=notification_id)
        )
    }


@router.patch("/{notification_id}", response_model=DataEnvelope[NotificationOut])
async def patch_notification_route(
    notification_id: UUID,
    payload: NotificationPatch,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, NotificationOut]:
    notification = await patch_notification(
        session,
        user_id=current_user.id,
        notification_id=notification_id,
        payload=payload,
        request_id=get_request_id(request),
    )
    return {"data": NotificationOut.model_validate(notification)}


@preferences_router.get("", response_model=DataEnvelope[list[NotificationPreferenceOut]])
async def get_preferences(
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, list[NotificationPreferenceOut]]:
    preferences = await ensure_notification_preferences(session, user_id=current_user.id)
    await session.commit()
    return {"data": [NotificationPreferenceOut.model_validate(item) for item in preferences]}


@preferences_router.put("", response_model=DataEnvelope[list[NotificationPreferenceOut]])
async def put_preferences(
    payload: NotificationPreferenceUpdateRequest,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, list[NotificationPreferenceOut]]:
    preferences = await update_notification_preferences(
        session,
        user_id=current_user.id,
        items=payload.items,
        request_id=get_request_id(request),
    )
    return {"data": [NotificationPreferenceOut.model_validate(item) for item in preferences]}
