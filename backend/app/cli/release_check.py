import argparse
import asyncio
import json
from collections import Counter
from typing import Any

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import BACKEND_ROOT, Settings, get_settings
from app.core.database import create_engine_for_settings
from app.core.release_gate import (
    ReleaseCheckItem,
    backup_status_item,
    private_beta_feature_matrix,
    production_settings_checks,
    tmp_dir_status_item,
)
from app.models.ai import AITask
from app.models.external_source import ExternalSource
from app.models.information import InformationItem
from app.models.market_data import MarketDataSource, StockDailySnapshot
from app.models.review_notification import DailyReview
from app.models.security_master import SecuritySourceRecord
from app.models.stock import Stock
from app.models.user import User
from app.models.watchlist import UserWatchlistItem
from app.providers.announcements.registry import provider_catalog
from app.providers.market_data.registry import market_data_provider_catalog
from app.providers.securities.registry import security_master_provider_catalog

TARGET_ALEMBIC_REVISION = "202607230008"


async def run_release_checks(settings: Settings) -> tuple[list[ReleaseCheckItem], dict[str, Any]]:
    items = production_settings_checks(settings)
    items.append(tmp_dir_status_item())
    items.append(backup_status_item())
    db_summary: dict[str, Any] = {"connected": False}
    engine = create_engine_for_settings(settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            db_summary["connected"] = True
            current_revision = await connection.run_sync(_current_alembic_revision)
        head_revision = _head_alembic_revision()
        db_summary["alembic_current"] = current_revision
        db_summary["alembic_head"] = head_revision
        db_summary["target_revision"] = TARGET_ALEMBIC_REVISION
        if current_revision != head_revision or current_revision != TARGET_ALEMBIC_REVISION:
            items.append(
                ReleaseCheckItem(
                    "ALEMBIC_NOT_AT_HEAD",
                    "fail",
                    "数据库迁移版本不是当前发布目标。",
                    {
                        "current": current_revision,
                        "head": head_revision,
                        "target": TARGET_ALEMBIC_REVISION,
                    },
                )
            )
        else:
            items.append(
                ReleaseCheckItem(
                    "ALEMBIC_AT_HEAD",
                    "pass",
                    "数据库迁移版本已到发布目标。",
                    {"current": current_revision},
                )
            )
        async with session_factory() as session:
            items.extend(await _database_state_checks(session, settings))
    except Exception as exc:  # noqa: BLE001
        items.append(
            ReleaseCheckItem(
                "DATABASE_CHECK_FAILED",
                "fail",
                "发布检查无法完成数据库连通性或状态读取。",
                {"error_type": type(exc).__name__},
            )
        )
    finally:
        await engine.dispose()

    metadata = {
        "app_env": settings.app_env,
        "database": db_summary,
        "providers": {
            "market_data": _safe_provider_catalog(market_data_provider_catalog(settings)),
            "announcement": provider_catalog(settings),
            "security_master": security_master_provider_catalog(settings),
        },
        "feature_matrix": private_beta_feature_matrix(settings),
    }
    return items, metadata


def _current_alembic_revision(sync_connection) -> str | None:
    return MigrationContext.configure(sync_connection).get_current_revision()


def _head_alembic_revision() -> str | None:
    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(alembic_cfg)
    return script.get_current_head()


async def _database_state_checks(session, settings: Settings) -> list[ReleaseCheckItem]:
    items: list[ReleaseCheckItem] = []
    admin_count = (
        await session.execute(
            select(func.count()).select_from(User).where(User.role == "admin", User.status == "active")
        )
    ).scalar_one()
    items.append(
        ReleaseCheckItem(
            "ADMIN_USER_EXISTS" if admin_count else "ADMIN_USER_MISSING",
            "pass" if admin_count else "fail",
            "存在可用管理员账户。" if admin_count else "生产发布前必须创建至少一个可用管理员账户。",
            {"admin_count": admin_count},
        )
    )

    stock_count = (await session.execute(select(func.count()).select_from(Stock))).scalar_one()
    source_record_count = (await session.execute(select(func.count()).select_from(SecuritySourceRecord))).scalar_one()
    source_codes = list(
        (
            await session.execute(select(Stock.source_code).where(Stock.source_code.is_not(None)).distinct())
        ).scalars()
    )
    if stock_count == 0:
        items.append(ReleaseCheckItem("SECURITY_MASTER_EMPTY", "warning", "证券主数据为空，真实自选股搜索将不可用。"))
    else:
        items.append(
            ReleaseCheckItem(
                "SECURITY_MASTER_READABLE",
                "pass",
                "证券主数据可读取。",
                {"stock_count": stock_count, "source_record_count": source_record_count, "source_codes": source_codes},
            )
        )
    if "BAOSTOCK_DEVELOPMENT_FALLBACK" in source_codes:
        items.append(
            ReleaseCheckItem(
                "SECURITY_MASTER_HAS_DEVELOPMENT_FALLBACK_ROWS",
                "warning",
                "证券目录中存在 BaoStock 开发补充记录；生产展示必须标记为 development_fallback，不得称为官方来源。",
            )
        )

    if settings.security_master_baostock_enabled:
        items.append(
            ReleaseCheckItem(
                "BAOSTOCK_CONFIG_ENABLED",
                "fail",
                "生产环境不得启用 BaoStock development fallback 同步。",
            )
        )

    external_rows = list(
        (
            await session.execute(
                select(ExternalSource.source_code, ExternalSource.enabled, ExternalSource.authorization_status)
                .where(ExternalSource.source_code.in_(["CNINFO", "SSE_DISCLOSURE", "BSE_DISCLOSURE"]))
                .order_by(ExternalSource.source_code)
            )
        ).all()
    )
    items.append(
        ReleaseCheckItem(
            "OFFICIAL_ANNOUNCEMENT_SOURCE_STATE",
            "pass",
            "公告来源注册状态已读取。",
            {
                "sources": [
                    {"source_code": row[0], "enabled": row[1], "authorization_status": row[2]}
                    for row in external_rows
                ]
            },
        )
    )

    market_rows = list(
        (
            await session.execute(
                select(
                    MarketDataSource.source_code,
                    MarketDataSource.authorization_status,
                    MarketDataSource.production_enabled,
                ).order_by(MarketDataSource.source_code)
            )
        ).all()
    )
    if any(row[2] and row[1] != "commercially_authorized" for row in market_rows):
        items.append(
            ReleaseCheckItem(
                "UNAUTHORIZED_MARKET_SOURCE_PRODUCTION_ENABLED",
                "fail",
                "存在未商业授权却标记为 production_enabled 的行情来源。",
            )
        )
    else:
        items.append(
            ReleaseCheckItem(
                "MARKET_DATA_CLOSED_OR_AUTHORIZED",
                "pass",
                "行情来源未生产启用，或均已标记商业授权。",
                {
                    "sources": [
                        {
                            "source_code": row[0],
                            "authorization_status": row[1],
                            "production_enabled": row[2],
                        }
                        for row in market_rows
                    ]
                },
            )
        )

    counts = await _core_table_counts(session)
    items.append(
        ReleaseCheckItem(
            "CORE_TABLE_COUNTS",
            "pass",
            "核心表计数已读取。",
            counts,
        )
    )
    return items


async def _core_table_counts(session) -> dict[str, int]:
    tables = {
        "users": User,
        "stocks": Stock,
        "watchlist_items": UserWatchlistItem,
        "information_items": InformationItem,
        "user_daily_reviews": DailyReview,
        "ai_tasks": AITask,
        "stock_daily_snapshots": StockDailySnapshot,
    }
    counts: dict[str, int] = {}
    for name, model in tables.items():
        counts[name] = (await session.execute(select(func.count()).select_from(model))).scalar_one()
    return counts


def _safe_provider_catalog(items: list[dict[str, object]]) -> list[dict[str, object]]:
    safe_items: list[dict[str, object]] = []
    for item in items:
        safe = dict(item)
        safe.pop("token", None)
        safe_items.append(safe)
    return safe_items


def _summary_payload(items: list[ReleaseCheckItem], metadata: dict[str, Any]) -> dict[str, Any]:
    counts = Counter(item.status for item in items)
    overall_status = "fail" if counts["fail"] else "warning" if counts["warning"] else "pass"
    return {
        "status": overall_status,
        "counts": {"pass": counts["pass"], "warning": counts["warning"], "fail": counts["fail"]},
        "checks": [item.as_dict() for item in items],
        "metadata": metadata,
    }


def _exit_code(items: list[ReleaseCheckItem]) -> int:
    if any(item.status == "fail" for item in items):
        return 1
    if any(item.status == "warning" for item in items):
        return 2
    return 0


async def _main_async(_args: argparse.Namespace) -> int:
    settings = get_settings()
    items, metadata = await run_release_checks(settings)
    print(json.dumps(_summary_payload(items, metadata), ensure_ascii=False, default=str, sort_keys=True))
    return _exit_code(items)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run non-mutating GeniusTrader production release checks")
    raise SystemExit(asyncio.run(_main_async(parser.parse_args())))


if __name__ == "__main__":
    main()
