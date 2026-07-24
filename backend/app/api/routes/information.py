from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from app.api.dependencies import CurrentUser, SessionDependency, SettingsDependency, get_request_id
from app.schemas.common import DataEnvelope, MessageResponse, Page
from app.schemas.information import (
    InformationAnalyzeRequest,
    InformationContentCreate,
    InformationContentOut,
    InformationDetailOut,
    InformationPatch,
    InformationStockRelationOut,
    InformationSummaryOut,
    ManualInformationCreate,
    StockRelationCreate,
    StockRelationPatch,
    UrlInformationCreate,
)
from app.services.information import (
    add_information_content,
    add_stock_relation,
    analyze_information_item,
    build_information_detail,
    create_manual_information,
    create_url_information,
    delete_stock_relation,
    fetch_information_item,
    list_information_items,
    patch_information_item,
    patch_stock_relation,
)

router = APIRouter()


@router.post("/manual", response_model=DataEnvelope[InformationDetailOut], status_code=status.HTTP_201_CREATED)
async def create_manual(
    payload: ManualInformationCreate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, InformationDetailOut]:
    item = await create_manual_information(
        session,
        user_id=current_user.id,
        title=payload.title,
        text=payload.text,
        source_type=payload.source_type,
        source_name=payload.source_name,
        published_at=payload.published_at,
        user_note=payload.user_note,
        related_stock_ids=payload.related_stock_ids,
        settings=settings,
        request_id=get_request_id(request),
    )
    if payload.analyze_now:
        await analyze_information_item(
            session,
            user_id=current_user.id,
            item_id=item.id,
            force=False,
            settings=settings,
            request_id=get_request_id(request),
        )
    detail = await build_information_detail(session, user_id=current_user.id, item_id=item.id)
    return {"data": detail}


@router.post("/url", response_model=DataEnvelope[InformationDetailOut], status_code=status.HTTP_201_CREATED)
async def create_from_url(
    payload: UrlInformationCreate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, InformationDetailOut]:
    item = await create_url_information(
        session,
        user_id=current_user.id,
        url=str(payload.url),
        source_type=payload.source_type,
        user_note=payload.user_note,
        related_stock_ids=payload.related_stock_ids,
        fetch_now=payload.fetch_now,
        settings=settings,
        request_id=get_request_id(request),
    )
    detail = await build_information_detail(session, user_id=current_user.id, item_id=item.id)
    return {"data": detail}


@router.get("", response_model=DataEnvelope[Page[InformationSummaryOut]])
async def list_items(
    session: SessionDependency,
    current_user: CurrentUser,
    status_value: Annotated[str | None, Query(alias="status", max_length=32)] = None,
    source_type: Annotated[str | None, Query(max_length=32)] = None,
    stock_id: UUID | None = None,
    is_important: bool | None = None,
    is_read: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Page[InformationSummaryOut]]:
    items, total = await list_information_items(
        session,
        user_id=current_user.id,
        status=status_value,
        source_type=source_type,
        stock_id=stock_id,
        is_important=is_important,
        is_read=is_read,
        date_from=date_from,
        date_to=date_to,
        q=q,
        limit=limit,
        offset=offset,
    )
    return {
        "data": Page(
            items=[InformationSummaryOut.model_validate(item) for item in items],
            limit=limit,
            offset=offset,
            total=total,
        )
    }


@router.get("/{item_id}", response_model=DataEnvelope[InformationDetailOut])
async def get_item(
    item_id: UUID,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, InformationDetailOut]:
    return {"data": await build_information_detail(session, user_id=current_user.id, item_id=item_id)}


@router.patch("/{item_id}", response_model=DataEnvelope[InformationDetailOut])
async def patch_item(
    item_id: UUID,
    payload: InformationPatch,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, InformationDetailOut]:
    item = await patch_information_item(
        session,
        user_id=current_user.id,
        item_id=item_id,
        title=payload.title,
        user_note=payload.user_note,
        is_important=payload.is_important,
        is_read=payload.is_read,
        archived=payload.archived,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": await build_information_detail(session, user_id=current_user.id, item_id=item.id)}


@router.post("/{item_id}/content", response_model=DataEnvelope[InformationContentOut], status_code=201)
async def add_content(
    item_id: UUID,
    payload: InformationContentCreate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, InformationContentOut]:
    content = await add_information_content(
        session,
        user_id=current_user.id,
        item_id=item_id,
        title=payload.title,
        text=payload.text,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": InformationContentOut.model_validate(content)}


@router.post("/{item_id}/fetch", response_model=DataEnvelope[InformationDetailOut])
async def fetch_item(
    item_id: UUID,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, InformationDetailOut]:
    item = await fetch_information_item(
        session,
        user_id=current_user.id,
        item_id=item_id,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": await build_information_detail(session, user_id=current_user.id, item_id=item.id)}


@router.post("/{item_id}/analyze", response_model=DataEnvelope[InformationDetailOut])
async def analyze_item(
    item_id: UUID,
    payload: InformationAnalyzeRequest,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, InformationDetailOut]:
    await analyze_information_item(
        session,
        user_id=current_user.id,
        item_id=item_id,
        force=payload.force,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": await build_information_detail(session, user_id=current_user.id, item_id=item_id)}


@router.post(
    "/{item_id}/stock-relations",
    response_model=DataEnvelope[InformationStockRelationOut],
    status_code=201,
)
async def add_relation(
    item_id: UUID,
    payload: StockRelationCreate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, InformationStockRelationOut]:
    relation = await add_stock_relation(
        session,
        user_id=current_user.id,
        item_id=item_id,
        payload=payload,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": InformationStockRelationOut.model_validate(relation)}


@router.patch("/{item_id}/stock-relations/{relation_id}", response_model=DataEnvelope[InformationStockRelationOut])
async def patch_relation(
    item_id: UUID,
    relation_id: UUID,
    payload: StockRelationPatch,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, InformationStockRelationOut]:
    relation = await patch_stock_relation(
        session,
        user_id=current_user.id,
        item_id=item_id,
        relation_id=relation_id,
        payload=payload,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": InformationStockRelationOut.model_validate(relation)}


@router.delete("/{item_id}/stock-relations/{relation_id}", response_model=DataEnvelope[MessageResponse])
async def delete_relation(
    item_id: UUID,
    relation_id: UUID,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, MessageResponse]:
    await delete_stock_relation(
        session,
        user_id=current_user.id,
        item_id=item_id,
        relation_id=relation_id,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": MessageResponse()}
