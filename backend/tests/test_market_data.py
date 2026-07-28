from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

import app.services.market_data as market_data_service
from app.core.config import get_settings
from app.core.time import utc_now
from app.models.market_data import MarketDataSyncRun, StockDailySnapshot
from app.models.watchlist import UserWatchlistItem
from app.providers.announcements.bse import BseAnnouncementProvider
from app.providers.announcements.models import RawAnnouncementRecord
from app.providers.market_data.mock import MockMarketDataProvider
from app.providers.market_data.models import MarketDataQuery
from app.providers.market_data.normalization import decimal_times, normalize_tushare_symbol
from app.providers.market_data.registry import market_data_provider_catalog
from app.services.market_data import start_market_data_sync
from tests.conftest import create_user, login, seed_stock, unique_username

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _enable_market_mock(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_DATA_SYNC_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_MOCK_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_REAL_NETWORK_ENABLED", "false")
    get_settings.cache_clear()


def _enable_tushare(monkeypatch, *, token: str = "", production: bool = False, authorization: str = "unverified") -> None:
    monkeypatch.setenv("MARKET_DATA_SYNC_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_TUSHARE_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_REAL_NETWORK_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_TUSHARE_TOKEN", token)
    monkeypatch.setenv("MARKET_DATA_TUSHARE_AUTHORIZATION_STATUS", authorization)
    monkeypatch.setenv("APP_ENV", "production" if production else "development")
    get_settings.cache_clear()


async def test_market_data_status_defaults_to_unverified_tushare(client, db_session):
    user = await create_user(db_session, username=unique_username("md_status"), password="UserPass123")
    await login(client, username=user.username, password="UserPass123")

    response = await client.get("/api/v1/market-data/status")

    assert response.status_code == 200
    data = response.json()["data"]
    source = {item["source_code"]: item for item in data["sources"]}["TUSHARE_PRO"]
    assert source["authorization_status"] == "unverified"
    assert source["production_enabled"] is False
    assert source["usage_scope"] == ["local_development", "internal_testing"]
    assert data["production_authorization_pending"] is True
    assert data["latest_trade_date"] is None


async def test_tushare_no_token_returns_provider_not_configured_without_snapshots(monkeypatch, client, db_session):
    _enable_tushare(monkeypatch, token="")
    admin = await create_user(db_session, username=unique_username("md_admin"), password="AdminPass123", role="admin")
    await seed_stock(db_session, symbol="600519", exchange="SH", name="贵州茅台")
    await login(client, username=admin.username, password="AdminPass123")

    response = await client.post(
        "/api/v1/admin/market-data/sync",
        json={"source_code": "TUSHARE_PRO", "use_current_watchlist": False},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MARKET_DATA_PROVIDER_NOT_CONFIGURED"
    assert (await db_session.execute(select(func.count()).select_from(StockDailySnapshot))).scalar_one() == 0


async def test_tushare_production_rejects_unverified_authorization(monkeypatch, client, db_session):
    _enable_tushare(monkeypatch, token="secret-token-not-printed", production=True, authorization="unverified")
    admin = await create_user(db_session, username=unique_username("md_prod"), password="AdminPass123", role="admin")
    await seed_stock(db_session, symbol="600519", exchange="SH", name="贵州茅台")
    await login(client, username=admin.username, password="AdminPass123")

    response = await client.post(
        "/api/v1/admin/market-data/sync",
        json={"source_code": "TUSHARE_PRO", "use_current_watchlist": False},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "MARKET_DATA_PERMISSION_DENIED"
    assert "secret-token-not-printed" not in response.text


async def test_development_mock_provider_sync_is_idempotent_and_preserves_units(monkeypatch, db_session):
    _enable_market_mock(monkeypatch)
    admin = await create_user(db_session, username=unique_username("md_sync"), password="AdminPass123", role="admin")
    stock = await seed_stock(db_session, symbol="600519", exchange="SH", name="贵州茅台")

    first = await start_market_data_sync(
        db_session,
        admin_user=admin,
        source_code="MOCK_MARKET_DATA",
        sync_mode="selected_trade_date",
        trade_date=date(2026, 7, 24),
        lookback_days=1,
        stock_ids=[stock.id],
        use_current_watchlist=False,
        dry_run=False,
        trigger_type="manual_admin",
        settings=get_settings(),
        request_id="test",
    )
    second = await start_market_data_sync(
        db_session,
        admin_user=admin,
        source_code="MOCK_MARKET_DATA",
        sync_mode="selected_trade_date",
        trade_date=date(2026, 7, 24),
        lookback_days=1,
        stock_ids=[stock.id],
        use_current_watchlist=False,
        dry_run=False,
        trigger_type="manual_admin",
        settings=get_settings(),
        request_id="test-2",
    )

    snapshot = (await db_session.execute(select(StockDailySnapshot))).scalar_one()
    assert first.status == "complete"
    assert first.created_count == 1
    assert second.status == "complete"
    assert second.created_count == 0
    assert second.unchanged_count == 1
    assert snapshot.source_code == "MOCK_MARKET_DATA"
    assert snapshot.volume == Decimal("1000000.0000")
    assert snapshot.amount == Decimal("10000000.0000")
    assert snapshot.pct_change is not None


async def test_market_sync_running_guard_blocks_same_source_and_date(monkeypatch, db_session):
    _enable_market_mock(monkeypatch)
    admin = await create_user(db_session, username=unique_username("md_running"), password="AdminPass123", role="admin")
    stock = await seed_stock(db_session, symbol="000001", exchange="SZ", name="平安银行")
    db_session.add(
        MarketDataSyncRun(
            source_code="MOCK_MARKET_DATA",
            trigger_type="manual_admin",
            sync_mode="selected_trade_date",
            status="running",
            requested_trade_date=date(2026, 7, 24),
            resolved_trade_date=date(2026, 7, 24),
            lookback_days=1,
            requested_symbol_count=1,
            received_count=0,
            created_count=0,
            updated_count=0,
            unchanged_count=0,
            failure_count=0,
            metrics={},
            started_at=utc_now(),
        )
    )
    await db_session.commit()

    with pytest.raises(Exception) as exc:
        await start_market_data_sync(
            db_session,
            admin_user=admin,
            source_code="MOCK_MARKET_DATA",
            sync_mode="selected_trade_date",
            trade_date=date(2026, 7, 24),
            lookback_days=1,
            stock_ids=[stock.id],
            use_current_watchlist=False,
            dry_run=False,
            trigger_type="manual_admin",
            settings=get_settings(),
            request_id="test-running",
        )

    assert exc.value.code.value == "MARKET_DATA_SYNC_ALREADY_RUNNING"


async def test_market_sync_failure_does_not_clear_old_snapshot(monkeypatch, db_session):
    _enable_market_mock(monkeypatch)
    admin = await create_user(db_session, username=unique_username("md_fail"), password="AdminPass123", role="admin")
    stock = await seed_stock(db_session, symbol="600519", exchange="SH", name="贵州茅台")
    await start_market_data_sync(
        db_session,
        admin_user=admin,
        source_code="MOCK_MARKET_DATA",
        sync_mode="selected_trade_date",
        trade_date=date(2026, 7, 24),
        lookback_days=1,
        stock_ids=[stock.id],
        use_current_watchlist=False,
        dry_run=False,
        trigger_type="manual_admin",
        settings=get_settings(),
        request_id="test-ok",
    )

    class FailingProvider(MockMarketDataProvider):
        async def fetch_daily_snapshots(self, query: MarketDataQuery):
            raise RuntimeError("network down")

    monkeypatch.setattr(market_data_service, "get_market_data_provider", lambda *_args: FailingProvider())
    failed = await start_market_data_sync(
        db_session,
        admin_user=admin,
        source_code="MOCK_MARKET_DATA",
        sync_mode="selected_trade_date",
        trade_date=date(2026, 7, 25),
        lookback_days=1,
        stock_ids=[stock.id],
        use_current_watchlist=False,
        dry_run=False,
        trigger_type="manual_admin",
        settings=get_settings(),
        request_id="test-fail",
    )

    assert failed.status == "network_error"
    assert (await db_session.execute(select(func.count()).select_from(StockDailySnapshot))).scalar_one() == 1


async def test_market_snapshot_api_uses_current_user_watchlist_isolation(monkeypatch, client, db_session):
    _enable_market_mock(monkeypatch)
    admin = await create_user(db_session, username=unique_username("md_admin_api"), password="AdminPass123", role="admin")
    user_a = await create_user(db_session, username=unique_username("md_user_a"), password="UserPass123")
    user_b = await create_user(db_session, username=unique_username("md_user_b"), password="UserPass123")
    stock_a = await seed_stock(db_session, symbol="600519", exchange="SH", name="贵州茅台")
    stock_b = await seed_stock(db_session, symbol="300750", exchange="SZ", name="宁德时代")
    db_session.add_all(
        [
            UserWatchlistItem(user_id=user_a.id, stock_id=stock_a.id, sort_order=0),
            UserWatchlistItem(user_id=user_b.id, stock_id=stock_b.id, sort_order=0),
        ]
    )
    await db_session.commit()
    await start_market_data_sync(
        db_session,
        admin_user=admin,
        source_code="MOCK_MARKET_DATA",
        sync_mode="selected_trade_date",
        trade_date=date(2026, 7, 24),
        lookback_days=1,
        stock_ids=[stock_a.id, stock_b.id],
        use_current_watchlist=False,
        dry_run=False,
        trigger_type="manual_admin",
        settings=get_settings(),
        request_id="test-api",
    )

    await login(client, username=user_a.username, password="UserPass123")
    response_a = await client.get("/api/v1/watchlist/market-snapshots")
    await login(client, username=user_b.username, password="UserPass123")
    response_b = await client.get("/api/v1/watchlist/market-snapshots")

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert [item["stock"]["symbol"] for item in response_a.json()["data"]] == ["600519.SH"]
    assert [item["stock"]["symbol"] for item in response_b.json()["data"]] == ["300750.SZ"]


async def test_market_data_admin_permissions_and_csrf(monkeypatch, client, db_session):
    _enable_market_mock(monkeypatch)
    user = await create_user(db_session, username=unique_username("md_perm"), password="UserPass123")
    admin = await create_user(db_session, username=unique_username("md_perm_admin"), password="AdminPass123", role="admin")
    await seed_stock(db_session, symbol="600519", exchange="SH", name="贵州茅台")

    await login(client, username=user.username, password="UserPass123")
    forbidden = await client.post("/api/v1/admin/market-data/sync", json={"source_code": "MOCK_MARKET_DATA"})
    assert forbidden.status_code == 403

    await login(client, username=admin.username, password="AdminPass123")
    client.headers.pop("X-CSRF-Token", None)
    missing_csrf = await client.post("/api/v1/admin/market-data/sync", json={"source_code": "MOCK_MARKET_DATA"})
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["error"]["code"] == "CSRF_TOKEN_REQUIRED"


async def test_market_data_normalization_handles_sh_sz_bj_and_tushare_units():
    assert normalize_tushare_symbol("600519.SH") == "600519.SH"
    assert normalize_tushare_symbol("000001.SZ") == "000001.SZ"
    assert normalize_tushare_symbol("920118.BJ") == "920118.BJ"
    assert decimal_times("123.45", "100") == Decimal("12345.00")
    assert decimal_times("3.5", "1000") == Decimal("3500.0")


async def test_market_data_provider_catalog_redacts_authorization_details(monkeypatch):
    _enable_tushare(monkeypatch, token="secret-token-not-printed")
    catalog = market_data_provider_catalog(get_settings())
    text = str(catalog)
    assert "secret-token-not-printed" not in text
    assert "TUSHARE_PRO" in text
    assert "unverified" in text


async def test_bse_announcement_provider_normalizes_current_bj_symbol_only():
    provider = BseAnnouncementProvider(get_settings())
    normalized = provider.normalize(
        RawAnnouncementRecord(
            provider_record_id="bse-1",
            title="北交所公司年度报告",
            published_at="2026-07-24",
            source_page_url="https://www.bse.cn/disclosure/announcement.html",
            document_url="https://www.bse.cn/disclosure/bse-1.pdf",
            company_name="北证样本",
            stock_symbols=["920118.BJ", "not-a-symbol"],
            exchange="BJ",
            raw_payload={"id": "bse-1"},
        )
    )

    assert normalized.source_code == "BSE_DISCLOSURE"
    assert normalized.stock_symbols == ["920118.BJ"]
    assert normalized.exchange == "BJ"
