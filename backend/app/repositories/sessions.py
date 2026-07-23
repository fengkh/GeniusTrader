import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.time import utc_now
from app.models.session import UserSession


async def get_session_by_token_hash(
    session: AsyncSession,
    token_hash: str,
) -> UserSession | None:
    result = await session.execute(
        select(UserSession).options(joinedload(UserSession.user)).where(UserSession.token_hash == token_hash)
    )
    return result.scalar_one_or_none()


async def revoke_session_by_id(session: AsyncSession, session_id: uuid.UUID) -> None:
    await session.execute(
        update(UserSession)
        .where(UserSession.id == session_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )


async def revoke_other_sessions(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    keep_session_id: uuid.UUID,
) -> None:
    await session.execute(
        update(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.id != keep_session_id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=utc_now())
    )
