from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUser, SessionDependency, SettingsDependency
from app.core.errors import AppError, ErrorCode
from app.repositories.stocks import get_stock_by_id, list_stocks
from app.schemas.common import DataEnvelope, Page
from app.schemas.market_data import StockMarketSnapshotOut
from app.schemas.stock import StockRead
from app.schemas.workbench import StockResearchDossierOut
from app.services.market_data import get_stock_market_snapshot
from app.services.research_workbench import build_stock_research_dossier

router = APIRouter()


@router.get("", response_model=DataEnvelope[Page[StockRead]])
async def list_stock_catalog(
    session: SessionDependency,
    current_user: CurrentUser,
    q: Annotated[str | None, Query(max_length=64)] = None,
    exchange: Annotated[str | None, Query(max_length=8)] = None,
    market: Annotated[str | None, Query(max_length=32)] = None,
    board: Annotated[str | None, Query(max_length=32)] = None,
    listing_status: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Page[StockRead]]:
    del current_user
    items, total = await list_stocks(
        session,
        q=q,
        exchange=exchange,
        market=market,
        board=board,
        listing_status=listing_status,
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


@router.get("/search", response_model=DataEnvelope[Page[StockRead]])
async def search_stock_catalog(
    session: SessionDependency,
    current_user: CurrentUser,
    q: Annotated[str | None, Query(max_length=64)] = None,
    exchange: Annotated[str | None, Query(max_length=8)] = None,
    board: Annotated[str | None, Query(max_length=32)] = None,
    listing_status: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Page[StockRead]]:
    del current_user
    items, total = await list_stocks(
        session,
        q=q,
        exchange=exchange,
        market="A_SHARE",
        board=board,
        listing_status=listing_status,
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


@router.get("/{stock_id}/market-snapshot", response_model=DataEnvelope[StockMarketSnapshotOut])
async def get_stock_market_data_snapshot(
    stock_id: UUID,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, StockMarketSnapshotOut]:
    del current_user
    return {"data": await get_stock_market_snapshot(session, stock_id=stock_id)}


@router.get("/{stock_id}/research-dossier", response_model=DataEnvelope[StockResearchDossierOut])
async def get_stock_research_dossier(
    stock_id: UUID,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, StockResearchDossierOut]:
    return {
        "data": await build_stock_research_dossier(
            session,
            user_id=current_user.id,
            stock_id=stock_id,
            settings=settings,
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
