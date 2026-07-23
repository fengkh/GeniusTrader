# ruff: noqa: I001
from datetime import UTC

from fastapi import APIRouter, Request, Response

from app.api.dependencies import CurrentSessionUser, SessionDependency, SettingsDependency, get_request_id
from app.schemas.auth import AuthUserResponse, ChangePasswordRequest, LoginRequest, LoginResponse
from app.schemas.common import DataEnvelope, MessageResponse
from app.schemas.user import CurrentUserRead
from app.services.auth import change_password, login_user, logout_session

router = APIRouter()


@router.post("/login", response_model=DataEnvelope[LoginResponse])
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: SettingsDependency,
    session: SessionDependency,
) -> dict[str, LoginResponse]:
    user, token, session_row = await login_user(
        session,
        username=payload.username,
        password=payload.password,
        settings=settings,
        request_id=get_request_id(request),
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_seconds,
        expires=session_row.expires_at.astimezone(UTC),
    )
    return {
        "data": LoginResponse(
            user=CurrentUserRead.model_validate(user),
            must_change_password=user.must_change_password,
        )
    }


@router.post("/logout", response_model=DataEnvelope[MessageResponse])
async def logout(
    request: Request,
    response: Response,
    settings: SettingsDependency,
    session: SessionDependency,
) -> dict[str, MessageResponse]:
    await logout_session(
        session,
        token=request.cookies.get(settings.session_cookie_name),
        request_id=get_request_id(request),
    )
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    return {"data": MessageResponse()}


@router.get("/me", response_model=DataEnvelope[AuthUserResponse])
async def me(current: CurrentSessionUser) -> dict[str, AuthUserResponse]:
    user, _ = current
    return {"data": AuthUserResponse(user=CurrentUserRead.model_validate(user))}


@router.post("/change-password", response_model=DataEnvelope[MessageResponse])
async def change_password_route(
    payload: ChangePasswordRequest,
    request: Request,
    current: CurrentSessionUser,
    session: SessionDependency,
) -> dict[str, MessageResponse]:
    user, session_row = current
    await change_password(
        session,
        user=user,
        current_session_id=session_row.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
        request_id=get_request_id(request),
    )
    return {"data": MessageResponse()}
