from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.api.dependencies import (
    AdminUser,
    CurrentUser,
    SessionDependency,
    SettingsDependency,
    get_request_id,
)
from app.schemas.common import DataEnvelope, Page
from app.schemas.market_data import (
    MarketDataStatusOut,
    MarketDataSyncRequest,
    MarketDataSyncRunOut,
)
from app.services.market_data import (
    get_market_data_status,
    list_market_data_sync_runs,
    start_market_data_sync,
)

router = APIRouter()
admin_router = APIRouter()


@router.get("/status", response_model=DataEnvelope[MarketDataStatusOut])
async def get_status(
    session: SessionDependency,
    settings: SettingsDependency,
    current_user: CurrentUser,
) -> dict[str, MarketDataStatusOut]:
    del current_user
    return {"data": await get_market_data_status(session, settings=settings)}


@admin_router.post("/sync", response_model=DataEnvelope[MarketDataSyncRunOut], status_code=status.HTTP_201_CREATED)
async def sync_market_data(
    payload: MarketDataSyncRequest,
    request: Request,
    session: SessionDependency,
    admin_user: AdminUser,
    settings: SettingsDependency,
) -> dict[str, MarketDataSyncRunOut]:
    run = await start_market_data_sync(
        session,
        admin_user=admin_user,
        source_code=payload.source_code,
        sync_mode=payload.sync_mode,
        trade_date=payload.trade_date,
        lookback_days=payload.lookback_days,
        stock_ids=payload.stock_ids,
        use_current_watchlist=payload.use_current_watchlist,
        dry_run=payload.dry_run,
        trigger_type="manual_admin",
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": MarketDataSyncRunOut.model_validate(run)}


@admin_router.get("/sync-runs", response_model=DataEnvelope[Page[MarketDataSyncRunOut]])
async def get_sync_runs(
    session: SessionDependency,
    admin_user: AdminUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Page[MarketDataSyncRunOut]]:
    del admin_user
    items, total = await list_market_data_sync_runs(session, limit=limit, offset=offset)
    return {
        "data": Page(
            items=[MarketDataSyncRunOut.model_validate(item) for item in items],
            limit=limit,
            offset=offset,
            total=total,
        )
    }
