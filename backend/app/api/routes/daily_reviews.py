from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from app.api.dependencies import CurrentUser, SessionDependency, SettingsDependency, get_request_id
from app.schemas.common import DataEnvelope, Page
from app.schemas.daily_review import (
    DailyReviewDetailOut,
    DailyReviewGenerateRequest,
    DailyReviewPatch,
    DailyReviewSummaryOut,
    DailyReviewVersionOut,
)
from app.services.daily_reviews import (
    archive_daily_review,
    build_daily_review_detail,
    default_review_date,
    generate_daily_review,
    get_daily_review_version,
    list_daily_reviews,
)

router = APIRouter()


@router.get("", response_model=DataEnvelope[Page[DailyReviewSummaryOut]])
async def list_reviews(
    session: SessionDependency,
    current_user: CurrentUser,
    status_value: Annotated[str | None, Query(alias="status", max_length=32)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Page[DailyReviewSummaryOut]]:
    items, total = await list_daily_reviews(
        session,
        user_id=current_user.id,
        status=status_value,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return {"data": Page(items=items, limit=limit, offset=offset, total=total)}


@router.post("", response_model=DataEnvelope[DailyReviewDetailOut], status_code=status.HTTP_201_CREATED)
async def generate_review(
    payload: DailyReviewGenerateRequest,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, DailyReviewDetailOut]:
    review = await generate_daily_review(
        session,
        user_id=current_user.id,
        review_date=payload.review_date or default_review_date(settings),
        force=payload.force,
        use_ai=payload.use_ai,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": review}


@router.get("/{review_id}", response_model=DataEnvelope[DailyReviewDetailOut])
async def get_review(
    review_id: UUID,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, DailyReviewDetailOut]:
    return {
        "data": await build_daily_review_detail(
            session,
            user_id=current_user.id,
            review_id=review_id,
            settings=settings,
            request_id=get_request_id(request),
        )
    }


@router.patch("/{review_id}", response_model=DataEnvelope[DailyReviewDetailOut])
async def patch_review(
    review_id: UUID,
    payload: DailyReviewPatch,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, DailyReviewDetailOut]:
    return {
        "data": await archive_daily_review(
            session,
            user_id=current_user.id,
            review_id=review_id,
            archived=payload.archived,
            settings=settings,
            request_id=get_request_id(request),
        )
    }


@router.post("/{review_id}/regenerate", response_model=DataEnvelope[DailyReviewDetailOut])
async def regenerate_review(
    review_id: UUID,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
    use_ai: bool = True,
) -> dict[str, DailyReviewDetailOut]:
    existing = await build_daily_review_detail(
        session,
        user_id=current_user.id,
        review_id=review_id,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {
        "data": await generate_daily_review(
            session,
            user_id=current_user.id,
            review_date=existing.review_date,
            force=True,
            use_ai=use_ai,
            settings=settings,
            request_id=get_request_id(request),
        )
    }


@router.get("/{review_id}/versions", response_model=DataEnvelope[list[DailyReviewVersionOut]])
async def list_review_versions(
    review_id: UUID,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, list[DailyReviewVersionOut]]:
    detail = await build_daily_review_detail(
        session,
        user_id=current_user.id,
        review_id=review_id,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": detail.versions}


@router.get("/{review_id}/versions/{version_id}", response_model=DataEnvelope[DailyReviewVersionOut])
async def get_review_version(
    review_id: UUID,
    version_id: UUID,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, DailyReviewVersionOut]:
    return {
        "data": DailyReviewVersionOut.model_validate(
            await get_daily_review_version(
                session,
                user_id=current_user.id,
                review_id=review_id,
                version_id=version_id,
            )
        )
    }
