import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User, UserCredential


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(
        select(User).options(selectinload(User.credential)).where(User.username == username)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await session.execute(
        select(User).options(selectinload(User.credential)).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_credential_by_user_id(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> UserCredential | None:
    result = await session.execute(select(UserCredential).where(UserCredential.user_id == user_id))
    return result.scalar_one_or_none()
