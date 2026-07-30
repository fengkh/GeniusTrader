# ruff: noqa: I001
import os
import asyncio
import sys
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
LOCAL_DATABASE_ENV = REPO_ROOT / ".local" / "database.env"
TRUNCATE_TABLES = [
    "audit_logs",
    "information_ingestion_links",
    "stock_daily_snapshots",
    "market_data_sync_runs",
    "security_source_records",
    "security_master_sync_runs",
    "user_announcement_candidates",
    "announcement_records",
    "provider_sync_states",
    "provider_sync_runs",
    "market_data_sources",
    "notification_deliveries",
    "notifications",
    "notification_preferences",
    "business_events",
    "research_task_updates",
    "research_tasks",
    "daily_review_items",
    "daily_review_versions",
    "daily_reviews",
    "verification_items",
    "information_entity_mentions",
    "information_stock_relations",
    "information_analysis_versions",
    "content_fetch_attempts",
    "information_contents",
    "information_sources",
    "ai_task_attempts",
    "ai_tasks",
    "ai_provider_configs",
    "information_items",
    "watchlist_item_tags",
    "user_watchlist_items",
    "user_tags",
    "watchlist_groups",
    "user_sessions",
    "user_credentials",
    "users",
    "stocks",
]


def _read_local_database_url() -> str | None:
    if "TEST_DATABASE_URL" in os.environ:
        return os.environ["TEST_DATABASE_URL"]
    if "DATABASE_URL" in os.environ:
        return make_url(os.environ["DATABASE_URL"]).set(database="geniustrader_test").render_as_string(hide_password=False)
    if not LOCAL_DATABASE_ENV.exists():
        return None
    for raw_line in LOCAL_DATABASE_ENV.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if line.startswith("DATABASE_URL="):
            return make_url(line.split("=", 1)[1]).set(database="geniustrader_test").render_as_string(hide_password=False)
    return None


TEST_DATABASE_URL = _read_local_database_url()
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("APP_ENCRYPTION_KEYS", Fernet.generate_key().decode("ascii"))
os.environ.setdefault("ALLOW_PRIVATE_AI_BASE_URL", "true")
os.environ["ANNOUNCEMENT_INGESTION_ENABLED"] = "false"
os.environ["ANNOUNCEMENT_REAL_NETWORK_ENABLED"] = "false"
os.environ["ANNOUNCEMENT_CNINFO_ENABLED"] = "false"
os.environ["ANNOUNCEMENT_SSE_ENABLED"] = "false"
os.environ["ANNOUNCEMENT_BSE_ENABLED"] = "false"
os.environ["ANNOUNCEMENT_DOCUMENT_EXTRACTION_ENABLED"] = "false"
os.environ["MARKET_DATA_SYNC_ENABLED"] = "false"
os.environ["MARKET_DATA_REAL_NETWORK_ENABLED"] = "false"
os.environ["MARKET_DATA_TUSHARE_ENABLED"] = "false"
os.environ["MARKET_DATA_MOCK_ENABLED"] = "false"
os.environ["MARKET_DATA_TUSHARE_TOKEN"] = ""
os.environ["SECURITY_MASTER_SYNC_ENABLED"] = "false"
os.environ["SECURITY_MASTER_REAL_NETWORK_ENABLED"] = "false"
os.environ["SECURITY_MASTER_SSE_ENABLED"] = "false"
os.environ["SECURITY_MASTER_SZSE_ENABLED"] = "false"
os.environ["SECURITY_MASTER_BSE_ENABLED"] = "false"
os.environ["SECURITY_MASTER_BAOSTOCK_ENABLED"] = "false"


def _test_database_available() -> bool:
    if not TEST_DATABASE_URL:
        return False
    url = make_url(TEST_DATABASE_URL)
    if not (url.database and url.database.endswith("_test")):
        raise RuntimeError("Refusing to run integration tests outside an explicit *_test database")
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"options": "-c timezone=utc"},
        pool_pre_ping=True,
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        return False
    finally:
        engine.dispose()
    return True


DB_AVAILABLE = _test_database_available()


def pytest_sessionstart(session) -> None:
    del session
    if not DB_AVAILABLE:
        pytest.exit(
            "geniustrader_test is not available; create it before running integration tests",
            returncode=0,
        )


def pytest_sessionfinish(session, exitstatus) -> None:
    del session, exitstatus
    try:
        from app.core.database import engine
    except Exception:
        return
    asyncio.run(engine.dispose())


@pytest.fixture(scope="session", autouse=True)
def migrated_test_database() -> None:
    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(autouse=True)
async def clean_test_database(migrated_test_database: None) -> AsyncGenerator[None, None]:
    from app.core.database import AsyncSessionLocal

    del migrated_test_database
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(f"TRUNCATE TABLE {', '.join(TRUNCATE_TABLES)} RESTART IDENTITY CASCADE")
        )
        await session.execute(
            text(
                "UPDATE external_sources SET enabled=false, health_status='unknown', "
                "authorization_status='review_required', redistribution_status='unclear', "
                "commercial_use_status='unclear', legal_review_status='pending', updated_at=now() "
                "WHERE source_code IN ('CNINFO', 'SSE_DISCLOSURE', 'BSE_DISCLOSURE')"
            )
        )
        await session.commit()
    yield


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as api_client:
        yield api_client


@pytest.fixture
async def db_session():
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


async def create_user(session, *, username: str, password: str, role: str = "user", status: str = "active"):
    from app.services.users import create_user as create_user_service

    user = await create_user_service(
        session,
        username=username,
        password=password,
        display_name=username,
        role=role,
        must_change_password=role != "admin",
        actor_user_id=None,
        request_id="test",
    )
    user.status = status
    await session.commit()
    await session.refresh(user)
    return user


async def seed_stock(session, *, symbol: str = "600519", exchange: str = "SH", name: str = "贵州茅台"):
    from app.models.stock import Stock
    from app.providers.securities.normalization import normalize_board, normalize_symbol, pinyin_fields

    code = symbol.split(".", 1)[0]
    full_symbol = symbol if "." in symbol else normalize_symbol(code, exchange)
    pinyin, initials = pinyin_fields(name)

    stock = Stock(
        symbol=full_symbol,
        code=code,
        exchange=exchange,
        name=name,
        market="A_SHARE",
        board=normalize_board(None, exchange=exchange, code=code),
        security_type="common_stock",
        short_name=name,
        full_name=name,
        listing_status="active",
        listed_at=None,
        aliases=[name],
        pinyin=pinyin,
        pinyin_initials=initials,
        source_code="test_seed",
        source_record_id=full_symbol,
        data_completeness="usable",
        is_searchable=True,
        list_status="listed",
        currency="CNY",
        data_source="test_seed",
    )
    session.add(stock)
    await session.commit()
    await session.refresh(stock)
    return stock


async def login(client: AsyncClient, *, username: str, password: str):
    response = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    csrf_token = client.cookies.get("geniustrader_csrf")
    if response.status_code == 200 and csrf_token:
        client.headers["X-CSRF-Token"] = csrf_token
    return response


def unique_username(prefix: str = "user") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
