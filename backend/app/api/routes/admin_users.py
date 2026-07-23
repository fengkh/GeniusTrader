from fastapi import APIRouter, Request

from app.api.dependencies import AdminUser, SessionDependency, get_request_id
from app.schemas.common import DataEnvelope
from app.schemas.user import AdminUserCreate, UserRead
from app.services.users import create_user

router = APIRouter()


@router.post("", response_model=DataEnvelope[UserRead], status_code=201)
async def create_regular_user(
    payload: AdminUserCreate,
    request: Request,
    admin: AdminUser,
    session: SessionDependency,
) -> dict[str, UserRead]:
    user = await create_user(
        session,
        username=payload.username,
        display_name=payload.display_name,
        password=payload.temporary_password,
        role="user",
        must_change_password=True,
        actor_user_id=admin.id,
        request_id=get_request_id(request),
    )
    await session.commit()
    await session.refresh(user)
    return {"data": UserRead.model_validate(user)}
