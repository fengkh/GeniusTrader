import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.audit import AuditLog

SENSITIVE_KEYS = {
    "password",
    "temporary_password",
    "current_password",
    "new_password",
    "password_hash",
    "token",
    "session_token",
    "cookie",
    "authorization",
    "database_url",
    "api_key",
}


def sanitize_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in SENSITIVE_KEYS:
                sanitized[key] = "[redacted]"
            else:
                sanitized[key] = sanitize_metadata(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_metadata(item) for item in value]
    return value


async def add_audit_log(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None,
    result: str,
    request_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            result=result,
            request_id=request_id,
            event_metadata=sanitize_metadata(metadata or {}),
            created_at=utc_now(),
        )
    )
