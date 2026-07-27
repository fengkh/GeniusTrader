import uuid

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.time import utc_now
from app.models.tag import UserTag, WatchlistItemTag
from app.models.watchlist import UserWatchlistItem, WatchlistGroup
from app.repositories.stocks import get_stock_by_id
from app.repositories.watchlist import (
    count_active_items,
    get_active_item_by_stock,
    get_archived_item_by_stock,
    get_default_group,
    get_group_for_user,
    get_item_for_user,
    get_tag_for_user,
    list_tags_by_ids,
    replace_item_tags,
)
from app.services.audit import add_audit_log

WATCHLIST_LIMIT = 200


def _unique_ids(values: list[uuid.UUID]) -> list[uuid.UUID]:
    return list(dict.fromkeys(values))


async def ensure_group(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    group_id: uuid.UUID | None,
) -> WatchlistGroup:
    if group_id:
        group = await get_group_for_user(session, user_id=user_id, group_id=group_id)
        if not group:
            raise AppError(ErrorCode.GROUP_NOT_FOUND, "分组不存在", status_code=404)
        return group
    default_group = await get_default_group(session, user_id)
    if not default_group:
        raise AppError(ErrorCode.GROUP_NOT_FOUND, "默认分组不存在", status_code=404)
    return default_group


async def ensure_tags(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tag_ids: list[uuid.UUID],
) -> list[UserTag]:
    unique = _unique_ids(tag_ids)
    tags = await list_tags_by_ids(session, user_id=user_id, tag_ids=unique)
    if len(tags) != len(unique):
        raise AppError(ErrorCode.TAG_NOT_FOUND, "标签不存在", status_code=404)
    return tags


async def tags_for_item(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
) -> list[UserTag]:
    result = await session.execute(
        select(UserTag)
        .join(WatchlistItemTag, WatchlistItemTag.tag_id == UserTag.id)
        .join(UserWatchlistItem, UserWatchlistItem.id == WatchlistItemTag.watchlist_item_id)
        .where(
            UserTag.user_id == user_id,
            UserWatchlistItem.user_id == user_id,
            UserWatchlistItem.id == item_id,
        )
        .order_by(UserTag.name)
    )
    return list(result.scalars().all())


async def attach_tags_to_items(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    items: list[UserWatchlistItem],
) -> None:
    for item in items:
        item.tags = await tags_for_item(session, user_id=user_id, item_id=item.id)


async def create_watchlist_item(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    stock_id: uuid.UUID,
    group_id: uuid.UUID | None,
    attention_reason: str | None,
    notes: str | None,
    tag_ids: list[uuid.UUID],
    settings: Settings,
    request_id: str | None,
) -> UserWatchlistItem:
    del settings
    from app.services.daily_reviews import mark_all_reviews_stale_for_user

    stock = await get_stock_by_id(session, stock_id)
    if not stock:
        raise AppError(ErrorCode.STOCK_NOT_FOUND, "股票不存在", status_code=404)
    if not stock.is_searchable:
        raise AppError(ErrorCode.STOCK_NOT_FOUND, "股票暂不可加入自选股", status_code=404)
    group = await ensure_group(session, user_id=user_id, group_id=group_id)
    tags = await ensure_tags(session, user_id=user_id, tag_ids=tag_ids)
    active = await get_active_item_by_stock(session, user_id=user_id, stock_id=stock_id)
    if active:
        active_id = active.id
        await add_audit_log(
            session,
            actor_user_id=user_id,
            action="watchlist.duplicate_add",
            target_type="watchlist_item",
            target_id=active_id,
            result="success",
            request_id=request_id,
        )
        await session.commit()
        return await get_item_or_404(session, user_id=user_id, item_id=active_id)
    if await count_active_items(session, user_id) >= WATCHLIST_LIMIT:
        raise AppError(ErrorCode.WATCHLIST_LIMIT_EXCEEDED, "自选股数量已达到上限", status_code=429)

    archived = await get_archived_item_by_stock(session, user_id=user_id, stock_id=stock_id)
    if archived:
        archived.group_id = group.id
        archived.attention_reason = attention_reason
        archived.notes = notes
        archived.archived_at = None
        await replace_item_tags(session, item_id=archived.id, tag_ids=[tag.id for tag in tags])
        await add_audit_log(
            session,
            actor_user_id=user_id,
            action="watchlist.restore",
            target_type="watchlist_item",
            target_id=archived.id,
            result="success",
            request_id=request_id,
        )
        await mark_all_reviews_stale_for_user(
            session,
            user_id=user_id,
            reason="watchlist_restored",
            request_id=request_id,
        )
        await session.commit()
        await session.refresh(archived)
        archived.stock = stock
        archived.group = group
        archived.tags = tags
        return archived

    item = UserWatchlistItem(
        user_id=user_id,
        stock_id=stock_id,
        group_id=group.id,
        attention_reason=attention_reason,
        notes=notes,
        sort_order=0,
    )
    session.add(item)
    try:
        await session.flush()
        await replace_item_tags(session, item_id=item.id, tag_ids=[tag.id for tag in tags])
    except IntegrityError as exc:
        raise AppError(
            ErrorCode.WATCHLIST_ITEM_ALREADY_EXISTS,
            "该股票已在自选股中",
            status_code=409,
        ) from exc
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="watchlist.create",
        target_type="watchlist_item",
        target_id=item.id,
        result="success",
        request_id=request_id,
    )
    await mark_all_reviews_stale_for_user(
        session,
        user_id=user_id,
        reason="watchlist_created",
        request_id=request_id,
    )
    await session.commit()
    await session.refresh(item)
    item.stock = stock
    item.group = group
    item.tags = tags
    return item


async def get_item_or_404(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    include_archived: bool = False,
) -> UserWatchlistItem:
    item = await get_item_for_user(
        session,
        user_id=user_id,
        item_id=item_id,
        include_archived=include_archived,
    )
    if not item:
        raise AppError(
            ErrorCode.WATCHLIST_ITEM_NOT_FOUND,
            "自选股记录不存在",
            status_code=404,
        )
    item.tags = await tags_for_item(session, user_id=user_id, item_id=item.id)
    return item


async def update_watchlist_item(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    group_id: uuid.UUID | None = None,
    attention_reason: str | None = None,
    notes: str | None = None,
    sort_order: int | None = None,
    tag_ids: list[uuid.UUID] | None = None,
    settings: Settings | None = None,
    request_id: str | None,
) -> UserWatchlistItem:
    del settings
    from app.services.daily_reviews import mark_all_reviews_stale_for_user

    item = await get_item_or_404(session, user_id=user_id, item_id=item_id)
    if item.archived_at:
        raise AppError(ErrorCode.WATCHLIST_ITEM_NOT_FOUND, "自选股记录不存在", status_code=404)
    if group_id is not None:
        item.group_id = (await ensure_group(session, user_id=user_id, group_id=group_id)).id
    if attention_reason is not None:
        item.attention_reason = attention_reason
    if notes is not None:
        item.notes = notes
    if sort_order is not None:
        item.sort_order = sort_order
    if tag_ids is not None:
        tags = await ensure_tags(session, user_id=user_id, tag_ids=tag_ids)
        await replace_item_tags(session, item_id=item.id, tag_ids=[tag.id for tag in tags])
        item.tags = tags
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="watchlist.update",
        target_type="watchlist_item",
        target_id=item.id,
        result="success",
        request_id=request_id,
    )
    await mark_all_reviews_stale_for_user(
        session,
        user_id=user_id,
        reason="watchlist_updated",
        request_id=request_id,
    )
    await session.commit()
    return await get_item_or_404(session, user_id=user_id, item_id=item.id)


async def archive_watchlist_item(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    settings: Settings,
    request_id: str | None,
) -> None:
    del settings
    from app.services.daily_reviews import mark_all_reviews_stale_for_user

    item = await get_item_for_user(session, user_id=user_id, item_id=item_id, include_archived=True)
    if not item:
        raise AppError(
            ErrorCode.WATCHLIST_ITEM_NOT_FOUND,
            "自选股记录不存在",
            status_code=404,
        )
    if not item.archived_at:
        item.archived_at = utc_now()
        await add_audit_log(
            session,
            actor_user_id=user_id,
            action="watchlist.archive",
            target_type="watchlist_item",
            target_id=item.id,
            result="success",
            request_id=request_id,
        )
        await mark_all_reviews_stale_for_user(
            session,
            user_id=user_id,
            reason="watchlist_archived",
            request_id=request_id,
        )
        await session.commit()


async def delete_tag_for_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tag_id: uuid.UUID,
    request_id: str | None,
) -> None:
    tag = await get_tag_for_user(session, user_id=user_id, tag_id=tag_id)
    if not tag:
        raise AppError(ErrorCode.TAG_NOT_FOUND, "标签不存在", status_code=404)
    await session.execute(delete(WatchlistItemTag).where(WatchlistItemTag.tag_id == tag.id))
    await session.delete(tag)
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="tag.delete",
        target_type="tag",
        target_id=tag.id,
        result="success",
        request_id=request_id,
    )
    await session.commit()
