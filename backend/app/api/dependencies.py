from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.errors import AppError, ErrorCode
from app.models.session import UserSession
from app.models.user import User
from app.services.auth import authenticate_session


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


SettingsDependency = Annotated[Settings, Depends(get_settings)]
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_session_user(
    request: Request,
    settings: SettingsDependency,
    session: SessionDependency,
) -> tuple[User, UserSession]:
    token = request.cookies.get(settings.session_cookie_name)
    user, session_row = await authenticate_session(
        session,
        token=token,
        request_id=get_request_id(request),
    )
    request.state.user_id = user.id
    request.state.session_id = session_row.id
    return user, session_row


async def get_current_user(
    current: Annotated[tuple[User, UserSession], Depends(get_current_session_user)],
) -> User:
    return current[0]


async def require_active_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if user.status != "active":
        raise AppError(ErrorCode.ACCOUNT_DISABLED, "账户不可用", status_code=403)
    return user


async def require_admin(
    user: Annotated[User, Depends(require_active_user)],
) -> User:
    if user.role != "admin":
        raise AppError(ErrorCode.FORBIDDEN, "权限不足", status_code=403)
    return user


CurrentUser = Annotated[User, Depends(require_active_user)]
AdminUser = Annotated[User, Depends(require_admin)]
CurrentSessionUser = Annotated[tuple[User, UserSession], Depends(get_current_session_user)]
