import logging

from fastapi import APIRouter
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import SessionDependency
from app.core.database import check_database_ready
from app.core.errors import AppError, ErrorCode

router = APIRouter()
logger = logging.getLogger("app.health")


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(session: SessionDependency) -> dict[str, str]:
    try:
        await check_database_ready(session)
    except SQLAlchemyError as exc:
        logger.error(
            "database readiness check failed",
            extra={
                "error_code": ErrorCode.DATABASE_UNAVAILABLE.value,
                "db_error_type": type(exc).__name__,
            },
        )
        raise AppError(ErrorCode.DATABASE_UNAVAILABLE, "数据库暂时不可用", status_code=503) from exc
    return {"status": "ok", "database": "ok"}
