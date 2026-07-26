from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUser, SessionDependency, SettingsDependency
from app.schemas.common import DataEnvelope
from app.schemas.external_sources import (
    AnnouncementProviderOut,
    ExternalSourceOut,
    FutureSourceGroupOut,
)
from app.services.announcement_ingestion import (
    list_announcement_providers,
    list_external_sources,
    list_future_source_groups,
)

router = APIRouter()
providers_router = APIRouter()


@router.get("", response_model=DataEnvelope[list[ExternalSourceOut]])
async def get_external_sources(
    session: SessionDependency,
    current_user: CurrentUser,
    source_category: Annotated[str | None, Query(max_length=64)] = None,
    country_code: Annotated[str | None, Query(max_length=8)] = None,
    authority_level: Annotated[str | None, Query(max_length=64)] = None,
    source_tier: Annotated[str | None, Query(max_length=16)] = None,
    enabled: bool | None = None,
    experimental: bool | None = None,
) -> dict[str, list[ExternalSourceOut]]:
    del current_user
    rows = await list_external_sources(
        session,
        source_category=source_category,
        country_code=country_code,
        authority_level=authority_level,
        source_tier=source_tier,
        enabled=enabled,
        experimental=experimental,
    )
    return {"data": [ExternalSourceOut.model_validate(row) for row in rows]}


@router.get("/future-groups", response_model=DataEnvelope[list[FutureSourceGroupOut]])
async def get_future_source_groups(current_user: CurrentUser) -> dict[str, list[FutureSourceGroupOut]]:
    del current_user
    return {"data": list_future_source_groups()}


@providers_router.get("", response_model=DataEnvelope[list[AnnouncementProviderOut]])
async def get_announcement_providers(
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, list[AnnouncementProviderOut]]:
    del current_user
    return {"data": list_announcement_providers(settings)}

