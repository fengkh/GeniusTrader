import asyncio
import sys
from collections.abc import AsyncGenerator

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _connect_args() -> dict[str, str]:
    return {"options": "-c timezone=utc"}


def create_engine_for_settings(settings: Settings):
    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        connect_args=_connect_args(),
    )


def create_sync_engine_for_settings(settings: Settings, *, null_pool: bool = False):
    kwargs = {
        "echo": False,
        "pool_pre_ping": True,
        "connect_args": _connect_args(),
    }
    if null_pool:
        kwargs["poolclass"] = NullPool
    return create_engine(settings.database_url, **kwargs)


settings = get_settings()
engine = create_engine_for_settings(settings)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def check_database_ready(session: AsyncSession) -> bool:
    await session.execute(text("SELECT 1"))
    return True
