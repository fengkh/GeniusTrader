from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.api.dependencies import (
    AdminUser,
    CurrentUser,
    SessionDependency,
    SettingsDependency,
    get_request_id,
)
from app.schemas.common import DataEnvelope, Page
from app.schemas.security_master import (
    SecurityMasterProviderOut,
    SecurityMasterStatusOut,
    SecurityMasterSyncRequest,
    SecurityMasterSyncRunOut,
)
from app.services.security_master import (
    get_security_master_status,
    list_security_master_providers,
    list_security_master_sync_runs,
    start_security_master_sync,
)

router = APIRouter()
admin_router = APIRouter()


@router.get("/status", response_model=DataEnvelope[SecurityMasterStatusOut])
async def get_status(
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, SecurityMasterStatusOut]:
    del current_user
    return {"data": await get_security_master_status(session)}


@router.get("/providers", response_model=DataEnvelope[list[SecurityMasterProviderOut]])
async def get_providers(
    settings: SettingsDependency,
    current_user: CurrentUser,
) -> dict[str, list[SecurityMasterProviderOut]]:
    del current_user
    return {"data": list_security_master_providers(settings)}


@admin_router.post("/sync", response_model=DataEnvelope[SecurityMasterSyncRunOut], status_code=201)
async def sync_security_master(
    payload: SecurityMasterSyncRequest,
    request: Request,
    session: SessionDependency,
    admin_user: AdminUser,
    settings: SettingsDependency,
) -> dict[str, SecurityMasterSyncRunOut]:
    run = await start_security_master_sync(
        session,
        admin_user=admin_user,
        source_code=payload.source_code,
        exchanges=payload.exchanges,
        force=payload.force,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": SecurityMasterSyncRunOut.model_validate(run)}


@admin_router.get("/sync-runs", response_model=DataEnvelope[Page[SecurityMasterSyncRunOut]])
async def get_sync_runs(
    session: SessionDependency,
    admin_user: AdminUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Page[SecurityMasterSyncRunOut]]:
    del admin_user
    items, total = await list_security_master_sync_runs(session, limit=limit, offset=offset)
    return {
        "data": Page(
            items=[SecurityMasterSyncRunOut.model_validate(item) for item in items],
            limit=limit,
            offset=offset,
            total=total,
        )
    }
