import uuid

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.stock import Stock
from app.models.tag import UserTag, WatchlistItemTag
from app.models.watchlist import UserWatchlistItem, WatchlistGroup


def item_load_options():
    return (
        selectinload(UserWatchlistItem.stock),
        selectinload(UserWatchlistItem.group),
    )


async def get_default_group(session: AsyncSession, user_id: uuid.UUID) -> WatchlistGroup | None:
    result = await session.execute(
        select(WatchlistGroup).where(WatchlistGroup.user_id == user_id, WatchlistGroup.is_default.is_(True))
    )
    return result.scalar_one_or_none()


async def get_group_for_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    group_id: uuid.UUID,
) -> WatchlistGroup | None:
    result = await session.execute(
        select(WatchlistGroup).where(WatchlistGroup.id == group_id, WatchlistGroup.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_groups(session: AsyncSession, user_id: uuid.UUID) -> list[WatchlistGroup]:
    result = await session.execute(
        select(WatchlistGroup).where(WatchlistGroup.user_id == user_id).order_by(WatchlistGroup.sort_order, WatchlistGroup.name)
    )
    return list(result.scalars().all())


async def get_tag_for_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tag_id: uuid.UUID,
) -> UserTag | None:
    result = await session.execute(select(UserTag).where(UserTag.id == tag_id, UserTag.user_id == user_id))
    return result.scalar_one_or_none()


async def list_tags(session: AsyncSession, user_id: uuid.UUID) -> list[UserTag]:
    result = await session.execute(select(UserTag).where(UserTag.user_id == user_id).order_by(UserTag.name))
    return list(result.scalars().all())


async def list_tags_by_ids(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tag_ids: list[uuid.UUID],
) -> list[UserTag]:
    if not tag_ids:
        return []
    result = await session.execute(select(UserTag).where(UserTag.user_id == user_id, UserTag.id.in_(tag_ids)))
    return list(result.scalars().all())


async def count_active_items(session: AsyncSession, user_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(UserWatchlistItem)
        .where(UserWatchlistItem.user_id == user_id, UserWatchlistItem.archived_at.is_(None))
    )
    return result.scalar_one()


async def get_active_item_by_stock(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    stock_id: uuid.UUID,
) -> UserWatchlistItem | None:
    result = await session.execute(
        select(UserWatchlistItem).where(
            UserWatchlistItem.user_id == user_id,
            UserWatchlistItem.stock_id == stock_id,
            UserWatchlistItem.archived_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def get_archived_item_by_stock(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    stock_id: uuid.UUID,
) -> UserWatchlistItem | None:
    result = await session.execute(
        select(UserWatchlistItem).where(
            UserWatchlistItem.user_id == user_id,
            UserWatchlistItem.stock_id == stock_id,
            UserWatchlistItem.archived_at.is_not(None),
        )
    )
    return result.scalar_one_or_none()


async def get_item_for_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    include_archived: bool = False,
) -> UserWatchlistItem | None:
    statement = (
        select(UserWatchlistItem)
        .options(*item_load_options())
        .where(UserWatchlistItem.id == item_id, UserWatchlistItem.user_id == user_id)
    )
    if not include_archived:
        statement = statement.where(UserWatchlistItem.archived_at.is_(None))
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def list_items(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    group_id: uuid.UUID | None = None,
    tag_id: uuid.UUID | None = None,
    q: str | None = None,
    include_archived: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[UserWatchlistItem], int]:
    statement = select(UserWatchlistItem).join(Stock).options(*item_load_options()).where(UserWatchlistItem.user_id == user_id)
    count_statement: Select[tuple[int]] = (
        select(func.count()).select_from(UserWatchlistItem).join(Stock).where(UserWatchlistItem.user_id == user_id)
    )
    if not include_archived:
        statement = statement.where(UserWatchlistItem.archived_at.is_(None))
        count_statement = count_statement.where(UserWatchlistItem.archived_at.is_(None))
    if group_id:
        statement = statement.where(UserWatchlistItem.group_id == group_id)
        count_statement = count_statement.where(UserWatchlistItem.group_id == group_id)
    if tag_id:
        statement = statement.join(WatchlistItemTag, WatchlistItemTag.watchlist_item_id == UserWatchlistItem.id)
        count_statement = count_statement.join(
            WatchlistItemTag,
            WatchlistItemTag.watchlist_item_id == UserWatchlistItem.id,
        )
        statement = statement.where(WatchlistItemTag.tag_id == tag_id)
        count_statement = count_statement.where(WatchlistItemTag.tag_id == tag_id)
    if q:
        like = f"%{q.strip()}%"
        q_filter = or_(
            Stock.symbol.ilike(like),
            Stock.name.ilike(like),
            UserWatchlistItem.attention_reason.ilike(like),
            UserWatchlistItem.notes.ilike(like),
        )
        statement = statement.where(q_filter)
        count_statement = count_statement.where(q_filter)
    total = (await session.execute(count_statement)).scalar_one()
    statement = statement.order_by(UserWatchlistItem.sort_order, Stock.exchange, Stock.symbol).limit(limit).offset(offset)
    items = list((await session.execute(statement)).scalars().unique().all())
    return items, total


async def replace_item_tags(
    session: AsyncSession,
    *,
    item_id: uuid.UUID,
    tag_ids: list[uuid.UUID],
) -> None:
    await session.execute(delete(WatchlistItemTag).where(WatchlistItemTag.watchlist_item_id == item_id))
    for tag_id in tag_ids:
        session.add(WatchlistItemTag(watchlist_item_id=item_id, tag_id=tag_id))
