import uuid
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.security import (
    generate_csrf_token,
    generate_session_token,
    hash_csrf_token,
    hash_password,
    hash_session_token,
    validate_password_strength,
    verify_password,
)
from app.core.time import utc_now
from app.models.session import UserSession
from app.models.user import User
from app.repositories.sessions import (
    get_session_by_token_hash,
    revoke_other_sessions,
    revoke_session_by_id,
)
from app.repositories.users import get_credential_by_user_id, get_user_by_username
from app.services.audit import add_audit_log

MAX_LOGIN_FAILURES = 5
LOCK_MINUTES = 15
LAST_SEEN_UPDATE_SECONDS = 300
_DUMMY_HASH = hash_password("DummyPassword12345")


def _client_ip(headers: dict[str, str], fallback_host: str | None) -> str | None:
    forwarded = headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return fallback_host[:45] if fallback_host else None


async def login_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    settings: Settings,
    request_id: str | None,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[User, str, str, UserSession]:
    normalized = username.strip().lower()
    user = await get_user_by_username(session, normalized)
    if not user or not user.credential:
        verify_password(password, _DUMMY_HASH)
        raise AppError(ErrorCode.INVALID_CREDENTIALS, "用户名或密码错误", status_code=401)

    if user.status == "disabled":
        raise AppError(ErrorCode.ACCOUNT_DISABLED, "账户已停用", status_code=403)
    if user.status != "active":
        raise AppError(ErrorCode.ACCOUNT_LOCKED, "账户暂不可用", status_code=429)

    now = utc_now()
    credential = user.credential
    if credential.locked_until and credential.locked_until > now:
        raise AppError(ErrorCode.ACCOUNT_LOCKED, "连续登录失败次数过多，请稍后再试", status_code=429)

    if not verify_password(password, credential.password_hash):
        credential.failed_login_count += 1
        if credential.failed_login_count >= MAX_LOGIN_FAILURES:
            credential.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            await add_audit_log(
                session,
                actor_user_id=user.id,
                action="auth.login_locked",
                target_type="user",
                target_id=user.id,
                result="failure",
                request_id=request_id,
                metadata={"failed_login_count": credential.failed_login_count},
            )
            await session.commit()
            raise AppError(ErrorCode.ACCOUNT_LOCKED, "连续登录失败次数过多，请稍后再试", status_code=429)
        await add_audit_log(
            session,
            actor_user_id=user.id,
            action="auth.login_failed",
            target_type="user",
            target_id=user.id,
            result="failure",
            request_id=request_id,
            metadata={"failed_login_count": credential.failed_login_count},
        )
        await session.commit()
        raise AppError(ErrorCode.INVALID_CREDENTIALS, "用户名或密码错误", status_code=401)

    token = generate_session_token()
    csrf_token = generate_csrf_token()
    session_row = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        csrf_token_hash=hash_csrf_token(csrf_token),
        expires_at=now + timedelta(seconds=settings.session_ttl_seconds),
        last_seen_at=now,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:255] or None,
    )
    credential.failed_login_count = 0
    credential.locked_until = None
    user.last_login_at = now
    session.add(session_row)
    await add_audit_log(
        session,
        actor_user_id=user.id,
        action="auth.login_success",
        target_type="user",
        target_id=user.id,
        result="success",
        request_id=request_id,
    )
    await session.commit()
    await session.refresh(user)
    await session.refresh(session_row)
    return user, token, csrf_token, session_row


async def authenticate_session(
    session: AsyncSession,
    *,
    token: str | None,
    request_id: str | None = None,
) -> tuple[User, UserSession]:
    if not token:
        raise AppError(ErrorCode.SESSION_REQUIRED, "需要登录后访问", status_code=401)
    session_row = await get_session_by_token_hash(session, hash_session_token(token))
    if not session_row or session_row.revoked_at:
        raise AppError(ErrorCode.SESSION_REQUIRED, "需要登录后访问", status_code=401)
    now = utc_now()
    if session_row.expires_at <= now:
        raise AppError(ErrorCode.SESSION_EXPIRED, "登录已过期，请重新登录", status_code=401)
    if session_row.user.status == "disabled":
        raise AppError(ErrorCode.ACCOUNT_DISABLED, "账户已停用", status_code=403)
    if session_row.user.status != "active":
        raise AppError(ErrorCode.ACCOUNT_LOCKED, "账户暂不可用", status_code=429)
    if session_row.last_seen_at + timedelta(seconds=LAST_SEEN_UPDATE_SECONDS) <= now:
        session_row.last_seen_at = now
        await session.commit()
    return session_row.user, session_row


async def logout_session(
    session: AsyncSession,
    *,
    token: str | None,
    request_id: str | None,
) -> None:
    if not token:
        return
    session_row = await get_session_by_token_hash(session, hash_session_token(token))
    if not session_row:
        return
    if not session_row.revoked_at:
        await revoke_session_by_id(session, session_row.id)
        await add_audit_log(
            session,
            actor_user_id=session_row.user_id,
            action="auth.logout",
            target_type="session",
            target_id=session_row.id,
            result="success",
            request_id=request_id,
        )
        await session.commit()


async def change_password(
    session: AsyncSession,
    *,
    user: User,
    current_session_id: uuid.UUID,
    current_password: str,
    new_password: str,
    request_id: str | None,
) -> None:
    credential = await get_credential_by_user_id(session, user.id)
    if not credential or not verify_password(current_password, credential.password_hash):
        raise AppError(ErrorCode.INVALID_CREDENTIALS, "当前密码不正确", status_code=401)
    if verify_password(new_password, credential.password_hash):
        raise AppError(ErrorCode.VALIDATION_ERROR, "新密码不能与当前密码相同", status_code=422)
    validate_password_strength(new_password, user.username)
    credential.password_hash = hash_password(new_password)
    credential.password_changed_at = utc_now()
    credential.failed_login_count = 0
    credential.locked_until = None
    user.must_change_password = False
    await revoke_other_sessions(session, user_id=user.id, keep_session_id=current_session_id)
    await add_audit_log(
        session,
        actor_user_id=user.id,
        action="auth.password_changed",
        target_type="user",
        target_id=user.id,
        result="success",
        request_id=request_id,
    )
    await session.commit()
