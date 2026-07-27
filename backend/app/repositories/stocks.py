import uuid

from sqlalchemy import Select, String, case, cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock

SUPPORTED_STOCK_SECURITY_TYPES = ("common_stock",)
DEFAULT_SEARCHABLE_LISTING_STATUSES = ("active", "suspended", "risk_warning")


def _stock_filters(
    statement: Select[tuple[Stock]] | Select[tuple[int]],
    *,
    q: str | None,
    exchange: str | None,
    market: str | None,
    board: str | None = None,
    listing_status: str | None = None,
    searchable_only: bool = True,
):
    if q:
        normalized_q = q.strip()
        like = f"%{normalized_q}%"
        statement = statement.where(
            or_(
                Stock.symbol.ilike(like),
                Stock.code.ilike(like),
                Stock.name.ilike(like),
                Stock.short_name.ilike(like),
                Stock.full_name.ilike(like),
                Stock.pinyin.ilike(like),
                Stock.pinyin_initials.ilike(like),
                cast(Stock.aliases, String).ilike(like),
                cast(Stock.aliases, JSONB).contains([normalized_q]),
            )
        )
    if exchange:
        statement = statement.where(Stock.exchange == exchange.strip().upper())
    if market:
        statement = statement.where(Stock.market == market.strip())
    if board:
        statement = statement.where(Stock.board == board.strip())
    if listing_status:
        statement = statement.where(Stock.listing_status == listing_status.strip())
    else:
        statement = statement.where(Stock.listing_status.in_(DEFAULT_SEARCHABLE_LISTING_STATUSES))
    statement = statement.where(Stock.security_type.in_(SUPPORTED_STOCK_SECURITY_TYPES))
    if searchable_only:
        statement = statement.where(Stock.is_searchable.is_(True))
    return statement


async def list_stocks(
    session: AsyncSession,
    *,
    q: str | None = None,
    exchange: str | None = None,
    market: str | None = None,
    board: str | None = None,
    listing_status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Stock], int]:
    if not q or not q.strip():
        return [], 0
    count_statement = _stock_filters(
        select(func.count()).select_from(Stock),
        q=q,
        exchange=exchange,
        market=market,
        board=board,
        listing_status=listing_status,
    )
    total = (await session.execute(count_statement)).scalar_one()
    statement = _stock_filters(
        select(Stock),
        q=q,
        exchange=exchange,
        market=market,
        board=board,
        listing_status=listing_status,
    )
    normalized_q = q.strip().upper()
    rank = case(
        (func.upper(Stock.code) == normalized_q, 0),
        (func.upper(Stock.symbol) == normalized_q, 1),
        (Stock.listing_status == "active", 2),
        else_=3,
    )
    statement = statement.order_by(rank, Stock.exchange, Stock.code, Stock.id).limit(limit).offset(offset)
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
    normalized_symbol = symbol.strip().upper()
    normalized_exchange = exchange.strip().upper()
    result = await session.execute(
        select(Stock).where(
            or_(
                Stock.symbol == normalized_symbol,
                Stock.symbol == f"{normalized_symbol}.{normalized_exchange}",
                Stock.code == normalized_symbol,
            ),
            Stock.exchange == normalized_exchange,
        )
    )
    return result.scalar_one_or_none()
