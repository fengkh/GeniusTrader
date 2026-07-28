import json
from typing import Any

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.user import User


def print_summary(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True))


async def first_admin_user() -> User | None:
    async with AsyncSessionLocal() as session:
        return (
            await session.execute(
                select(User)
                .where(User.role == "admin", User.status == "active")
                .order_by(User.created_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
