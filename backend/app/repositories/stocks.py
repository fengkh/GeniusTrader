import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock


def _stock_filters(
    statement: Select[tuple[Stock]] | Select[tuple[int]],
    *,
    q: str | None,
    exchange: str | None,
    market: str | None,
):
    if q:
        like = f"%{q.strip()}%"
        statement = statement.where(or_(Stock.symbol.ilike(like), Stock.name.ilike(like)))
    if exchange:
        statement = statement.where(Stock.exchange == exchange.strip().upper())
    if market:
        statement = statement.where(Stock.market == market.strip())
    return statement


async def list_stocks(
    session: AsyncSession,
    *,
    q: str | None = None,
    exchange: str | None = None,
    market: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Stock], int]:
    count_statement = _stock_filters(select(func.count()).select_from(Stock), q=q, exchange=exchange, market=market)
    total = (await session.execute(count_statement)).scalar_one()
    statement = _stock_filters(select(Stock), q=q, exchange=exchange, market=market)
    statement = statement.order_by(Stock.exchange, Stock.symbol).limit(limit).offset(offset)
    items = list((await session.execute(statement)).scalars().all())
    return items, total


async def get_stock_by_id(session: AsyncSession, stock_id: uuid.UUID) -> Stock | None:
    result = await session.execute(select(Stock).where(Stock.id == stock_id))
    return result.scalar_one_or_none()


async def get_stock_by_symbol_exchange(
    session: AsyncSession,
    *,
    symbol: str,
    exchange: str,
) -> Stock | None:
    result = await session.execute(
        select(Stock).where(Stock.symbol == symbol.strip(), Stock.exchange == exchange.strip().upper())
    )
    return result.scalar_one_or_none()
