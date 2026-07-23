import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.core.security import hash_password, validate_password_strength
from app.core.time import utc_now
from app.models.user import User, UserCredential
from app.models.watchlist import WatchlistGroup
from app.repositories.users import get_user_by_username
from app.services.audit import add_audit_log

DEFAULT_GROUP_NAME = "默认分组"


def normalize_username(username: str) -> str:
    return username.strip().lower()


async def create_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    display_name: str | None = None,
    role: str = "user",
    must_change_password: bool = True,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> User:
    normalized_username = normalize_username(username)
    validate_password_strength(password, normalized_username)
    if role not in {"admin", "user"}:
        raise AppError(ErrorCode.VALIDATION_ERROR, "用户角色无效", status_code=422)
    existing_user = await get_user_by_username(session, normalized_username)
    if existing_user:
        raise AppError(ErrorCode.USERNAME_ALREADY_EXISTS, "用户名已存在", status_code=409)

    user = User(
        username=normalized_username,
        display_name=(display_name or normalized_username).strip(),
        role=role,
        status="active",
        must_change_password=must_change_password,
    )
    now = utc_now()
    credential = UserCredential(
        user=user,
        password_hash=hash_password(password),
        password_changed_at=now,
        failed_login_count=0,
    )
    default_group = WatchlistGroup(user=user, name=DEFAULT_GROUP_NAME, sort_order=0, is_default=True)
    session.add_all([user, credential, default_group])
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(ErrorCode.USERNAME_ALREADY_EXISTS, "用户名已存在", status_code=409) from exc
    await add_audit_log(
        session,
        actor_user_id=actor_user_id,
        action="user.create",
        target_type="user",
        target_id=user.id,
        result="success",
        request_id=request_id,
        metadata={"role": role},
    )
    return user
