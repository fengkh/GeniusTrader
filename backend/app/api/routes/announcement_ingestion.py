from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from app.api.dependencies import CurrentUser, SessionDependency, SettingsDependency, get_request_id
from app.schemas.announcement_ingestion import (
    AnnouncementCandidateDetailOut,
    AnnouncementCandidatePatch,
    AnnouncementCandidateSummaryOut,
    AnnouncementDocumentExtractOut,
    AnnouncementImportOut,
    AnnouncementImportRequest,
    AnnouncementSyncRunCreate,
    ProviderSyncRunOut,
)
from app.schemas.common import DataEnvelope, Page
from app.services.announcement_ingestion import (
    extract_candidate_document,
    get_announcement_candidate_detail,
    get_announcement_sync_run_or_404,
    import_announcement_candidate,
    list_announcement_candidates,
    list_announcement_sync_runs,
    patch_announcement_candidate_status,
    start_announcement_sync_run,
    sync_run_out,
)

sync_runs_router = APIRouter()
candidates_router = APIRouter()


@sync_runs_router.post("", response_model=DataEnvelope[ProviderSyncRunOut], status_code=status.HTTP_201_CREATED)
async def create_sync_run(
    payload: AnnouncementSyncRunCreate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, ProviderSyncRunOut]:
    run = await start_announcement_sync_run(
        session,
        user_id=current_user.id,
        source_code=payload.source_code,
        date_from=payload.date_from,
        date_to=payload.date_to,
        stock_ids=payload.stock_ids,
        use_current_watchlist=payload.use_current_watchlist,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": sync_run_out(run)}


@sync_runs_router.get("", response_model=DataEnvelope[Page[ProviderSyncRunOut]])
async def list_sync_runs(
    session: SessionDependency,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Page[ProviderSyncRunOut]]:
    runs, total = await list_announcement_sync_runs(session, user_id=current_user.id, limit=limit, offset=offset)
    return {"data": Page(items=[sync_run_out(run) for run in runs], limit=limit, offset=offset, total=total)}


@sync_runs_router.get("/{run_id}", response_model=DataEnvelope[ProviderSyncRunOut])
async def get_sync_run(
    run_id: UUID,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, ProviderSyncRunOut]:
    run = await get_announcement_sync_run_or_404(session, user_id=current_user.id, run_id=run_id)
    return {"data": sync_run_out(run)}


@candidates_router.get("", response_model=DataEnvelope[Page[AnnouncementCandidateSummaryOut]])
async def list_candidates(
    session: SessionDependency,
    current_user: CurrentUser,
    status_value: Annotated[str | None, Query(alias="status", max_length=32)] = None,
    source_code: Annotated[str | None, Query(max_length=80)] = None,
    stock_id: UUID | None = None,
    announcement_type: Annotated[str | None, Query(max_length=80)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Page[AnnouncementCandidateSummaryOut]]:
    candidates, total = await list_announcement_candidates(
        session,
        user_id=current_user.id,
        status=status_value,
        source_code=source_code,
        stock_id=stock_id,
        announcement_type=announcement_type,
        date_from=date_from,
        date_to=date_to,
        q=q,
        limit=limit,
        offset=offset,
    )
    return {"data": Page(items=candidates, limit=limit, offset=offset, total=total)}


@candidates_router.get("/{candidate_id}", response_model=DataEnvelope[AnnouncementCandidateDetailOut])
async def get_candidate(
    candidate_id: UUID,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, AnnouncementCandidateDetailOut]:
    return {"data": await get_announcement_candidate_detail(session, user_id=current_user.id, candidate_id=candidate_id)}


@candidates_router.patch("/{candidate_id}", response_model=DataEnvelope[AnnouncementCandidateDetailOut])
async def patch_candidate(
    candidate_id: UUID,
    payload: AnnouncementCandidatePatch,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, AnnouncementCandidateDetailOut]:
    detail = await patch_announcement_candidate_status(
        session,
        user_id=current_user.id,
        candidate_id=candidate_id,
        status=payload.status,
        request_id=get_request_id(request),
    )
    return {"data": detail}


@candidates_router.post("/{candidate_id}/extract-document", response_model=DataEnvelope[AnnouncementDocumentExtractOut])
async def extract_document(
    candidate_id: UUID,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, AnnouncementDocumentExtractOut]:
    result = await extract_candidate_document(
        session,
        user_id=current_user.id,
        candidate_id=candidate_id,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": result}


@candidates_router.post("/{candidate_id}/import", response_model=DataEnvelope[AnnouncementImportOut], status_code=201)
async def import_candidate(
    candidate_id: UUID,
    payload: AnnouncementImportRequest,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, AnnouncementImportOut]:
    result = await import_announcement_candidate(
        session,
        user_id=current_user.id,
        candidate_id=candidate_id,
        import_mode=payload.import_mode,
        title_override=payload.title_override,
        user_note=payload.user_note,
        supplemented_text=payload.supplemented_text,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": result}
