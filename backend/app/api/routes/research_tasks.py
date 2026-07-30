from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response, status

from app.api.dependencies import CurrentUser, SessionDependency, get_request_id
from app.schemas.common import DataEnvelope, Page
from app.schemas.research import (
    ResearchTaskCreate,
    ResearchTaskOut,
    ResearchTaskPatch,
    ResearchTaskStatusUpdate,
    ResearchTaskUpdateCreate,
)
from app.services.research_tasks import (
    add_research_task_update,
    create_research_task,
    dismiss_research_task,
    get_research_task_or_404,
    list_research_tasks,
    patch_research_task,
    update_research_task_status,
)

router = APIRouter()


@router.get("", response_model=DataEnvelope[Page[ResearchTaskOut]])
async def list_tasks(
    session: SessionDependency,
    current_user: CurrentUser,
    task_type: Annotated[str | None, Query(max_length=40)] = None,
    status_value: Annotated[str | None, Query(alias="status", max_length=40)] = None,
    priority: Annotated[str | None, Query(max_length=16)] = None,
    stock_id: UUID | None = None,
    due_date: date | None = None,
    source_type: Annotated[str | None, Query(max_length=40)] = None,
    keyword: Annotated[str | None, Query(max_length=100)] = None,
    open_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Page[ResearchTaskOut]]:
    return {
        "data": await list_research_tasks(
            session,
            user_id=current_user.id,
            task_type=task_type,
            status=status_value,
            priority=priority,
            stock_id=stock_id,
            due_date=due_date,
            source_type=source_type,
            keyword=keyword,
            open_only=open_only,
            limit=limit,
            offset=offset,
        )
    }


@router.post("", response_model=DataEnvelope[ResearchTaskOut], status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: ResearchTaskCreate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, ResearchTaskOut]:
    return {
        "data": await create_research_task(
            session,
            user_id=current_user.id,
            payload=payload,
            request_id=get_request_id(request),
        )
    }


@router.get("/{task_id}", response_model=DataEnvelope[ResearchTaskOut])
async def get_task(
    task_id: UUID,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, ResearchTaskOut]:
    return {"data": ResearchTaskOut.model_validate(await get_research_task_or_404(session, user_id=current_user.id, task_id=task_id))}


@router.patch("/{task_id}", response_model=DataEnvelope[ResearchTaskOut])
async def patch_task(
    task_id: UUID,
    payload: ResearchTaskPatch,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, ResearchTaskOut]:
    return {
        "data": await patch_research_task(
            session,
            user_id=current_user.id,
            task_id=task_id,
            payload=payload,
            request_id=get_request_id(request),
        )
    }


@router.post("/{task_id}/status", response_model=DataEnvelope[ResearchTaskOut])
async def set_task_status(
    task_id: UUID,
    payload: ResearchTaskStatusUpdate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, ResearchTaskOut]:
    return {
        "data": await update_research_task_status(
            session,
            user_id=current_user.id,
            task_id=task_id,
            payload=payload,
            request_id=get_request_id(request),
        )
    }


@router.post("/{task_id}/updates", response_model=DataEnvelope[ResearchTaskOut], status_code=status.HTTP_201_CREATED)
async def add_task_update(
    task_id: UUID,
    payload: ResearchTaskUpdateCreate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, ResearchTaskOut]:
    return {
        "data": await add_research_task_update(
            session,
            user_id=current_user.id,
            task_id=task_id,
            payload=payload,
            request_id=get_request_id(request),
        )
    }


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    request: Request,
    response: Response,
    session: SessionDependency,
    current_user: CurrentUser,
) -> Response:
    await dismiss_research_task(
        session,
        user_id=current_user.id,
        task_id=task_id,
        request_id=get_request_id(request),
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
