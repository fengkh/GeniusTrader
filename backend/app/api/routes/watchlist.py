from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, SessionDependency, SettingsDependency, get_request_id
from app.core.errors import AppError, ErrorCode
from app.models.tag import UserTag
from app.models.watchlist import UserWatchlistItem, WatchlistGroup
from app.repositories.watchlist import (
    get_group_for_user,
    get_tag_for_user,
    list_groups,
    list_items,
    list_tags,
)
from app.schemas.common import DataEnvelope, MessageResponse, Page
from app.schemas.market_data import WatchlistMarketSnapshotOut
from app.schemas.watchlist import (
    UserTagCreate,
    UserTagRead,
    UserTagUpdate,
    WatchlistGroupCreate,
    WatchlistGroupRead,
    WatchlistGroupUpdate,
    WatchlistItemCreate,
    WatchlistItemRead,
    WatchlistItemUpdate,
)
from app.schemas.workbench import WatchlistScannerOut
from app.services.audit import add_audit_log
from app.services.market_data import get_watchlist_market_snapshots
from app.services.research_workbench import build_watchlist_scanner
from app.services.watchlist import (
    archive_watchlist_item,
    attach_tags_to_items,
    create_watchlist_item,
    delete_tag_for_user,
    ensure_group,
    get_item_or_404,
    update_watchlist_item,
)

router = APIRouter()


@router.get("/groups", response_model=DataEnvelope[list[WatchlistGroupRead]])
async def get_groups(
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, list[WatchlistGroupRead]]:
    groups = await list_groups(session, current_user.id)
    return {"data": [WatchlistGroupRead.model_validate(group) for group in groups]}


@router.post("/groups", response_model=DataEnvelope[WatchlistGroupRead], status_code=201)
async def create_group(
    payload: WatchlistGroupCreate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, WatchlistGroupRead]:
    group = WatchlistGroup(
        user_id=current_user.id,
        name=payload.name,
        sort_order=payload.sort_order,
        is_default=False,
    )
    session.add(group)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, "分组名称已存在", status_code=409) from exc
    await add_audit_log(
        session,
        actor_user_id=current_user.id,
        action="group.create",
        target_type="watchlist_group",
        target_id=group.id,
        result="success",
        request_id=get_request_id(request),
    )
    await session.commit()
    await session.refresh(group)
    return {"data": WatchlistGroupRead.model_validate(group)}


@router.patch("/groups/{group_id}", response_model=DataEnvelope[WatchlistGroupRead])
async def update_group(
    group_id: UUID,
    payload: WatchlistGroupUpdate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, WatchlistGroupRead]:
    group = await get_group_for_user(session, user_id=current_user.id, group_id=group_id)
    if not group:
        raise AppError(ErrorCode.GROUP_NOT_FOUND, "分组不存在", status_code=404)
    if payload.name is not None:
        group.name = payload.name
    if payload.sort_order is not None:
        group.sort_order = payload.sort_order
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, "分组名称已存在", status_code=409) from exc
    await add_audit_log(
        session,
        actor_user_id=current_user.id,
        action="group.update",
        target_type="watchlist_group",
        target_id=group.id,
        result="success",
        request_id=get_request_id(request),
    )
    await session.commit()
    await session.refresh(group)
    return {"data": WatchlistGroupRead.model_validate(group)}


@router.delete("/groups/{group_id}", response_model=DataEnvelope[MessageResponse])
async def delete_group(
    group_id: UUID,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    move_to_group_id: UUID | None = None,
) -> dict[str, MessageResponse]:
    group = await get_group_for_user(session, user_id=current_user.id, group_id=group_id)
    if not group:
        raise AppError(ErrorCode.GROUP_NOT_FOUND, "分组不存在", status_code=404)
    if group.is_default:
        raise AppError(ErrorCode.VALIDATION_ERROR, "默认分组不能直接删除", status_code=422)
    active_count = (
        await session.execute(
            select(func.count())
            .select_from(UserWatchlistItem)
            .where(
                UserWatchlistItem.user_id == current_user.id,
                UserWatchlistItem.group_id == group.id,
                UserWatchlistItem.archived_at.is_(None),
            )
        )
    ).scalar_one()
    if active_count and not move_to_group_id:
        raise AppError(ErrorCode.VALIDATION_ERROR, "分组中仍有自选股，请指定迁移目标分组", status_code=422)
    if move_to_group_id:
        target = await ensure_group(session, user_id=current_user.id, group_id=move_to_group_id)
        if target.id == group.id:
            raise AppError(ErrorCode.VALIDATION_ERROR, "迁移目标分组无效", status_code=422)
        await session.execute(
            UserWatchlistItem.__table__.update()
            .where(UserWatchlistItem.user_id == current_user.id, UserWatchlistItem.group_id == group.id)
            .values(group_id=target.id)
        )
    await session.delete(group)
    await add_audit_log(
        session,
        actor_user_id=current_user.id,
        action="group.delete",
        target_type="watchlist_group",
        target_id=group.id,
        result="success",
        request_id=get_request_id(request),
    )
    await session.commit()
    return {"data": MessageResponse()}


@router.get("/tags", response_model=DataEnvelope[list[UserTagRead]])
async def get_tags(
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, list[UserTagRead]]:
    tags = await list_tags(session, current_user.id)
    return {"data": [UserTagRead.model_validate(tag) for tag in tags]}


@router.post("/tags", response_model=DataEnvelope[UserTagRead], status_code=201)
async def create_tag(
    payload: UserTagCreate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, UserTagRead]:
    tag = UserTag(user_id=current_user.id, name=payload.name)
    session.add(tag)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, "标签名称已存在", status_code=409) from exc
    await add_audit_log(
        session,
        actor_user_id=current_user.id,
        action="tag.create",
        target_type="tag",
        target_id=tag.id,
        result="success",
        request_id=get_request_id(request),
    )
    await session.commit()
    await session.refresh(tag)
    return {"data": UserTagRead.model_validate(tag)}


@router.patch("/tags/{tag_id}", response_model=DataEnvelope[UserTagRead])
async def update_tag(
    tag_id: UUID,
    payload: UserTagUpdate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, UserTagRead]:
    tag = await get_tag_for_user(session, user_id=current_user.id, tag_id=tag_id)
    if not tag:
        raise AppError(ErrorCode.TAG_NOT_FOUND, "标签不存在", status_code=404)
    tag.name = payload.name
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, "标签名称已存在", status_code=409) from exc
    await add_audit_log(
        session,
        actor_user_id=current_user.id,
        action="tag.update",
        target_type="tag",
        target_id=tag.id,
        result="success",
        request_id=get_request_id(request),
    )
    await session.commit()
    await session.refresh(tag)
    return {"data": UserTagRead.model_validate(tag)}


@router.delete("/tags/{tag_id}", response_model=DataEnvelope[MessageResponse])
async def delete_tag(
    tag_id: UUID,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, MessageResponse]:
    await delete_tag_for_user(
        session,
        user_id=current_user.id,
        tag_id=tag_id,
        request_id=get_request_id(request),
    )
    return {"data": MessageResponse()}


@router.get("", response_model=DataEnvelope[Page[WatchlistItemRead]])
async def get_watchlist(
    session: SessionDependency,
    current_user: CurrentUser,
    group_id: UUID | None = None,
    tag_id: UUID | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Page[WatchlistItemRead]]:
    if group_id and not await get_group_for_user(session, user_id=current_user.id, group_id=group_id):
        raise AppError(ErrorCode.GROUP_NOT_FOUND, "分组不存在", status_code=404)
    if tag_id and not await get_tag_for_user(session, user_id=current_user.id, tag_id=tag_id):
        raise AppError(ErrorCode.TAG_NOT_FOUND, "标签不存在", status_code=404)
    items, total = await list_items(
        session,
        user_id=current_user.id,
        group_id=group_id,
        tag_id=tag_id,
        q=q,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    await attach_tags_to_items(session, user_id=current_user.id, items=items)
    return {
        "data": Page(
            items=[WatchlistItemRead.model_validate(item) for item in items],
            limit=limit,
            offset=offset,
            total=total,
        )
    }


@router.get("/market-snapshots", response_model=DataEnvelope[list[WatchlistMarketSnapshotOut]])
async def get_watchlist_market_data_snapshots(
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, list[WatchlistMarketSnapshotOut]]:
    return {"data": await get_watchlist_market_snapshots(session, user_id=current_user.id)}


@router.get("/scanner", response_model=DataEnvelope[WatchlistScannerOut])
async def get_watchlist_scanner(
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
    keyword: Annotated[str | None, Query(max_length=100)] = None,
    group_id: UUID | None = None,
    tag_id: UUID | None = None,
    has_new_information: bool | None = None,
    has_pending_candidate: bool | None = None,
    has_open_task: bool | None = None,
    has_high_priority_task: bool | None = None,
    has_observation: bool | None = None,
    review_stale: bool | None = None,
    market_data_available: bool | None = None,
    market_movement: Annotated[str | None, Query(max_length=16)] = None,
    exchange: Annotated[str | None, Query(max_length=8)] = None,
    sort: Annotated[str, Query(max_length=40)] = "attention_score",
) -> dict[str, WatchlistScannerOut]:
    return {
        "data": await build_watchlist_scanner(
            session,
            user_id=current_user.id,
            keyword=keyword,
            group_id=group_id,
            tag_id=tag_id,
            has_new_information=has_new_information,
            has_pending_candidate=has_pending_candidate,
            has_open_task=has_open_task,
            has_high_priority_task=has_high_priority_task,
            has_observation=has_observation,
            review_stale=review_stale,
            market_data_available=market_data_available,
            market_movement=market_movement,
            exchange=exchange,
            sort=sort,
            settings=settings,
        )
    }


@router.post("", response_model=DataEnvelope[WatchlistItemRead], status_code=201)
async def add_watchlist_item(
    payload: WatchlistItemCreate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, WatchlistItemRead]:
    item = await create_watchlist_item(
        session,
        user_id=current_user.id,
        stock_id=payload.stock_id,
        group_id=payload.group_id,
        attention_reason=payload.attention_reason,
        notes=payload.notes,
        tag_ids=payload.tag_ids,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": WatchlistItemRead.model_validate(item)}


@router.get("/{item_id}", response_model=DataEnvelope[WatchlistItemRead])
async def get_watchlist_item(
    item_id: UUID,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, WatchlistItemRead]:
    item = await get_item_or_404(session, user_id=current_user.id, item_id=item_id)
    return {"data": WatchlistItemRead.model_validate(item)}


@router.patch("/{item_id}", response_model=DataEnvelope[WatchlistItemRead])
async def patch_watchlist_item(
    item_id: UUID,
    payload: WatchlistItemUpdate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, WatchlistItemRead]:
    item = await update_watchlist_item(
        session,
        user_id=current_user.id,
        item_id=item_id,
        group_id=payload.group_id,
        attention_reason=payload.attention_reason,
        notes=payload.notes,
        sort_order=payload.sort_order,
        tag_ids=payload.tag_ids,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": WatchlistItemRead.model_validate(item)}


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist_item(
    item_id: UUID,
    request: Request,
    response: Response,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> Response:
    await archive_watchlist_item(
        session,
        user_id=current_user.id,
        item_id=item_id,
        settings=settings,
        request_id=get_request_id(request),
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
