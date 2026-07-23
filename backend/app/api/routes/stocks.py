from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUser, SessionDependency
from app.core.errors import AppError, ErrorCode
from app.repositories.stocks import get_stock_by_id, list_stocks
from app.schemas.common import DataEnvelope, Page
from app.schemas.stock import StockRead

router = APIRouter()


@router.get("", response_model=DataEnvelope[Page[StockRead]])
async def list_stock_catalog(
    session: SessionDependency,
    current_user: CurrentUser,
    q: Annotated[str | None, Query(max_length=64)] = None,
    exchange: Annotated[str | None, Query(max_length=8)] = None,
    market: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Page[StockRead]]:
    del current_user
    items, total = await list_stocks(
        session,
        q=q,
        exchange=exchange,
        market=market,
        limit=limit,
        offset=offset,
    )
    return {
        "data": Page(
            items=[StockRead.model_validate(item) for item in items],
            limit=limit,
            offset=offset,
            total=total,
        )
    }


@router.get("/{stock_id}", response_model=DataEnvelope[StockRead])
async def get_stock(
    stock_id: UUID,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, StockRead]:
    del current_user
    stock = await get_stock_by_id(session, stock_id)
    if not stock:
        raise AppError(ErrorCode.STOCK_NOT_FOUND, "股票不存在", status_code=404)
    return {"data": StockRead.model_validate(stock)}
