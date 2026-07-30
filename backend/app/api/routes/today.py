from datetime import date

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUser, SessionDependency, SettingsDependency, get_request_id
from app.schemas.common import DataEnvelope
from app.schemas.workbench import TodayOverviewOut
from app.services.daily_reviews import default_review_date
from app.services.research_workbench import build_today_overview

router = APIRouter()


@router.get("/overview", response_model=DataEnvelope[TodayOverviewOut])
async def get_today_overview(
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
    business_date: date | None = None,
) -> dict[str, TodayOverviewOut]:
    return {
        "data": await build_today_overview(
            session,
            user_id=current_user.id,
            business_date=business_date or default_review_date(settings),
            settings=settings,
            request_id=get_request_id(request),
        )
    }
