import argparse
import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select

import app.cli.market_data_provider_smoke as market_data_smoke
import app.services.market_data as market_data_service
from app.core.config import get_settings
from app.core.time import utc_now
from app.models.ai import AITask
from app.models.market_data import MarketDataSyncRun, StockDailySnapshot
from app.models.research import ResearchTask
from app.models.review_notification import BusinessEvent, Notification
from app.models.watchlist import UserWatchlistItem
from app.providers.announcements.bse import BseAnnouncementProvider
from app.providers.announcements.models import RawAnnouncementRecord
from app.providers.market_data.akshare import AkShareMarketDataProvider
from app.providers.market_data.akshare_sina import AkShareSinaDailyMarketDataProvider
from app.providers.market_data.baostock import BaoStockMarketDataProvider
from app.providers.market_data.mock import MockMarketDataProvider
from app.providers.market_data.models import (
    DailyMarketSnapshotRecord,
    MarketDataProviderResult,
    MarketDataQuery,
    TradeCalendarDay,
)
from app.providers.market_data.normalization import decimal_times, normalize_tushare_symbol
from app.providers.market_data.registry import (
    market_data_provider_catalog,
    route_market_data_provider_for_symbol,
)
from app.providers.market_data.tushare import TushareMarketDataProvider
from app.providers.statuses import ProviderStatus
from app.services.market_data import start_market_data_sync
from tests.conftest import create_user, login, seed_stock, unique_username

pytestmark = pytest.mark.asyncio


class FakeFrame:
    def __init__(self, rows):
        self._rows = rows
        self.columns = list(rows[0].keys()) if rows else []
        self.empty = not rows

    def to_dict(self, orient):
        assert orient == "records"
        return self._rows


class FakeAkshareSmokeProvider:
    source_code = "AKSHARE_EASTMONEY"
    provider_adapter = "test.fake_akshare"

    def __init__(self) -> None:
        self.fetch_count = 0
        self.calendar_count = 0

    def capabilities(self) -> list[str]:
        return ["daily_snapshot", "trade_calendar"]

    async def health_check(self) -> MarketDataProviderResult:
        return MarketDataProviderResult(status=ProviderStatus.PASS)

    async def trade_calendar(self, query: MarketDataQuery) -> list[TradeCalendarDay]:
        self.calendar_count += 1
        trade_date = query.trade_date or date(2026, 7, 29)
        return [TradeCalendarDay(trade_date=trade_date, is_open=True, source_code=self.source_code)]

    async def fetch_daily_snapshots(self, query: MarketDataQuery) -> MarketDataProviderResult:
        self.fetch_count += 1
        records = [
            _daily_record(symbol=symbol, source_code=self.source_code, trade_date=query.trade_date)
            for symbol in query.symbols
            if query.trade_date is not None
        ]
        return MarketDataProviderResult(
            status=ProviderStatus.PASS,
            records=records,
            metrics={
                "attempt_counts": {record.symbol: 1 for record in records},
                "raw_units": {"volume": "lot", "amount": "CNY"},
                "normalized_units": {"volume": "share", "amount": "CNY"},
                "stage_events": [
                    {
                        "provider_code": self.source_code,
                        "symbol": record.symbol,
                        "trade_date": record.trade_date.isoformat(),
                        "stage": "stock_fetch_succeeded",
                        "attempt": 1,
                    }
                    for record in records
                ],
            },
            request_count=len(query.symbols),
            success_count=len(records),
        )


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _enable_market_mock(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_DATA_SYNC_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_PROVIDER_ENABLED", "false")
    monkeypatch.setenv("MARKET_DATA_MOCK_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_REAL_NETWORK_ENABLED", "false")
    get_settings.cache_clear()


def _enable_tushare(monkeypatch, *, token: str = "", production: bool = False, authorization: str = "unverified") -> None:
    monkeypatch.setenv("MARKET_DATA_SYNC_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_TUSHARE_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_REAL_NETWORK_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_TUSHARE_TOKEN", token)
    monkeypatch.setenv("MARKET_DATA_TUSHARE_AUTHORIZATION_STATUS", authorization)
    monkeypatch.setenv("APP_ENV", "production" if production else "development")
    get_settings.cache_clear()


def _enable_akshare(monkeypatch, *, production: bool = False) -> None:
    monkeypatch.setenv("MARKET_DATA_SYNC_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_AKSHARE_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_REAL_NETWORK_ENABLED", "true")
    monkeypatch.setenv("APP_ENV", "production" if production else "development")
    get_settings.cache_clear()


def _enable_akshare_sina(monkeypatch, *, production: bool = False) -> None:
    monkeypatch.setenv("MARKET_DATA_SYNC_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_AKSHARE_SINA_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_REAL_NETWORK_ENABLED", "true")
    monkeypatch.setenv("APP_ENV", "production" if production else "development")
    get_settings.cache_clear()


def _enable_baostock(monkeypatch, *, production: bool = False) -> None:
    monkeypatch.setenv("MARKET_DATA_SYNC_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_BAOSTOCK_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_REAL_NETWORK_ENABLED", "true")
    monkeypatch.setenv("APP_ENV", "production" if production else "development")
    get_settings.cache_clear()


def _daily_record(
    *,
    symbol: str,
    source_code: str = "AKSHARE_EASTMONEY",
    trade_date: date | None = None,
) -> DailyMarketSnapshotRecord:
    return DailyMarketSnapshotRecord(
        source_code=source_code,
        symbol=symbol,
        trade_date=trade_date or date(2026, 7, 29),
        open=Decimal("1680.00"),
        high=Decimal("1710.00"),
        low=Decimal("1670.00"),
        close=Decimal("1700.00"),
        pre_close=Decimal("1688.00"),
        change=Decimal("12.00"),
        pct_change=Decimal("0.71"),
        volume=Decimal("123400"),
        amount=Decimal("209780000"),
        turnover_rate=Decimal("0.41"),
        volume_ratio=None,
        total_market_value=None,
        circulating_market_value=None,
        pe_ttm=None,
        pb=None,
        is_trading=True,
        data_completeness="complete",
        source_updated_at=utc_now(),
        fetched_at=utc_now(),
        raw_metadata_hash=f"stable-{source_code}-{symbol}-{trade_date or date(2026, 7, 29)}",
        limitations=["test_record"],
        source_record_ref=f"{source_code}:{symbol}:{trade_date or date(2026, 7, 29)}",
    )


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


async def test_market_sync_requires_watchlist_or_explicit_stock_scope(monkeypatch, db_session):
    _enable_market_mock(monkeypatch)
    admin = await create_user(db_session, username=unique_username("md_scope"), password="AdminPass123", role="admin")
    await seed_stock(db_session, symbol="600000", exchange="SH", name="scope bank")

    with pytest.raises(Exception) as exc:
        await start_market_data_sync(
            db_session,
            admin_user=admin,
            source_code="MOCK_MARKET_DATA",
            sync_mode="selected_trade_date",
            trade_date=date(2026, 7, 24),
            lookback_days=1,
            stock_ids=[],
            use_current_watchlist=False,
            dry_run=False,
            trigger_type="manual_admin",
            settings=get_settings(),
            request_id="test-no-scope",
        )

    assert exc.value.code.value == "VALIDATION_ERROR"
    assert (await db_session.execute(select(func.count()).select_from(StockDailySnapshot))).scalar_one() == 0


async def test_market_sync_watchlist_scope_uses_only_admin_watchlist(monkeypatch, db_session):
    _enable_market_mock(monkeypatch)
    admin = await create_user(db_session, username=unique_username("md_watch_scope"), password="AdminPass123", role="admin")
    watched = await seed_stock(db_session, symbol="600519", exchange="SH", name="watched stock")
    unwatched = await seed_stock(db_session, symbol="300750", exchange="SZ", name="unwatched stock")
    db_session.add(UserWatchlistItem(user_id=admin.id, stock_id=watched.id, sort_order=0))
    await db_session.commit()

    run_row = await start_market_data_sync(
        db_session,
        admin_user=admin,
        source_code="MOCK_MARKET_DATA",
        sync_mode="selected_trade_date",
        trade_date=date(2026, 7, 24),
        lookback_days=1,
        stock_ids=[],
        use_current_watchlist=True,
        dry_run=False,
        trigger_type="manual_admin",
        settings=get_settings(),
        request_id="test-watch-scope",
    )

    snapshots = (await db_session.execute(select(StockDailySnapshot))).scalars().all()
    assert run_row.requested_symbol_count == 1
    assert {snapshot.stock_id for snapshot in snapshots} == {watched.id}
    assert unwatched.id not in {snapshot.stock_id for snapshot in snapshots}


async def test_tushare_normalization_preserves_units_without_printing_raw_token():
    provider = TushareMarketDataProvider(get_settings())

    record = provider._normalize_record(
        symbol="600519.SH",
        raw={
            "trade_date": "20260724",
            "open": "1680.10",
            "high": "1700.00",
            "low": "1668.00",
            "close": "1690.50",
            "pre_close": "1680.00",
            "change": "10.50",
            "pct_chg": "0.6250",
            "vol": "12345.67",
            "amount": "98765.43",
        },
        fetched_at=utc_now(),
    )

    assert record.volume == Decimal("1234567.0000")
    assert record.amount == Decimal("98765430.0000")
    assert record.turnover_rate is None
    assert record.total_market_value is None
    assert record.data_completeness == "complete"
    assert "[redacted]" not in repr(record)
    assert record.source_record_ref is not None


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


async def test_free_market_provider_catalog_is_unverified_and_production_closed(monkeypatch):
    _enable_akshare(monkeypatch)
    monkeypatch.setenv("MARKET_DATA_AKSHARE_SINA_ENABLED", "true")
    monkeypatch.setenv("MARKET_DATA_BAOSTOCK_ENABLED", "true")
    get_settings.cache_clear()

    catalog = {item["source_code"]: item for item in market_data_provider_catalog(get_settings())}

    assert catalog["AKSHARE_EASTMONEY"]["enabled_by_config"] is True
    assert catalog["AKSHARE_EASTMONEY"]["authorization_status"] == "unverified"
    assert catalog["AKSHARE_EASTMONEY"]["production_enabled"] is False
    assert catalog["AKSHARE_SINA_DAILY"]["enabled_by_config"] is True
    assert catalog["AKSHARE_SINA_DAILY"]["authorization_status"] == "unverified"
    assert catalog["AKSHARE_SINA_DAILY"]["production_enabled"] is False
    assert catalog["BAOSTOCK"]["authorization_status"] == "unverified"
    assert catalog["BAOSTOCK"]["production_enabled"] is False
    assert "official" in " ".join(catalog["AKSHARE_EASTMONEY"]["limitations"]).lower()


async def test_market_data_trial_route_maps_exchange_without_silent_fallback():
    assert route_market_data_provider_for_symbol("600519.SH") == "BAOSTOCK"
    assert route_market_data_provider_for_symbol("688981.SH") == "BAOSTOCK"
    assert route_market_data_provider_for_symbol("300750.SZ") == "BAOSTOCK"
    assert route_market_data_provider_for_symbol("920000.BJ") == "AKSHARE_SINA_DAILY"

    with pytest.raises(ValueError):
        route_market_data_provider_for_symbol("600519")


async def test_baostock_normalizes_turnover_ratio_and_computes_change(monkeypatch):
    _enable_baostock(monkeypatch)
    provider = BaoStockMarketDataProvider(get_settings())

    record = provider._normalize_record(
        symbol="600519.SH",
        target_date=date(2026, 7, 30),
        rows=[
            {
                "date": "2026-07-30",
                "open": "1680.00",
                "high": "1710.00",
                "low": "1670.00",
                "close": "1700.00",
                "preclose": "1688.00",
                "volume": "123400",
                "amount": "209780000",
                "pctChg": "0.71",
                "turn": "0.0125",
                "tradestatus": "1",
            }
        ],
    )

    assert record is not None
    assert record.source_code == "BAOSTOCK"
    assert record.trade_date == date(2026, 7, 30)
    assert record.turnover_rate == Decimal("1.2500")
    assert record.change == Decimal("12.00")
    assert record.volume == Decimal("123400")
    assert record.amount == Decimal("209780000")


async def test_akshare_sina_bj_daily_normalization_units_and_previous_close(monkeypatch):
    _enable_akshare_sina(monkeypatch)
    provider = AkShareSinaDailyMarketDataProvider(get_settings())
    calls: list[dict[str, str]] = []

    async def fake_call(_func_name, **kwargs):
        calls.append(kwargs)
        return FakeFrame(
            [
                {
                    "date": "2026-07-29",
                    "open": "19.80",
                    "high": "20.10",
                    "low": "19.50",
                    "close": "20.00",
                    "volume": "100000",
                    "amount": "2000000",
                    "outstanding_share": "500000000",
                    "turnover": "0.0100",
                },
                {
                    "date": "2026-07-30",
                    "open": "20.10",
                    "high": "21.00",
                    "low": "19.90",
                    "close": "20.50",
                    "volume": "120000",
                    "amount": "2460000",
                    "outstanding_share": "500000000",
                    "turnover": "0.0125",
                },
            ]
        )

    monkeypatch.setattr(provider, "_call_akshare", fake_call)

    result = await provider.fetch_daily_snapshots(
        MarketDataQuery(
            trade_date=date(2026, 7, 30),
            date_from=date(2026, 7, 29),
            date_to=date(2026, 7, 30),
            symbols=["920000.BJ"],
            max_records=1,
            dry_run=True,
        )
    )

    record = result.records[0]
    assert result.status == "pass"
    assert calls[0]["symbol"] == "bj920000"
    assert calls[0]["start_date"] == "20260729"
    assert calls[0]["end_date"] == "20260730"
    assert record.source_code == "AKSHARE_SINA_DAILY"
    assert record.symbol == "920000.BJ"
    assert record.pre_close == Decimal("20.00")
    assert record.change == Decimal("0.50")
    assert record.pct_change == Decimal("2.500")
    assert record.volume == Decimal("120000")
    assert record.amount == Decimal("2460000")
    assert record.turnover_rate == Decimal("1.2500")
    assert record.total_market_value is None
    assert result.metrics["raw_units"]["volume"] == "share"
    assert result.metrics["normalized_units"]["turnover_rate"] == "percent_number"


async def test_akshare_sina_marks_source_lag_when_target_date_missing(monkeypatch):
    _enable_akshare_sina(monkeypatch)
    provider = AkShareSinaDailyMarketDataProvider(get_settings())

    async def fake_call(_func_name, **_kwargs):
        return FakeFrame(
            [
                {
                    "date": "2026-07-29",
                    "open": "19.80",
                    "high": "20.10",
                    "low": "19.50",
                    "close": "20.00",
                    "volume": "100000",
                    "amount": "2000000",
                    "turnover": "0.0100",
                }
            ]
        )

    monkeypatch.setattr(provider, "_call_akshare", fake_call)

    result = await provider.fetch_daily_snapshots(
        MarketDataQuery(
            trade_date=date(2026, 7, 30),
            date_from=date(2026, 7, 29),
            date_to=date(2026, 7, 30),
            symbols=["920000.BJ"],
            max_records=1,
            dry_run=True,
        )
    )

    assert result.status == "data_insufficient"
    assert result.records == []
    assert result.errors[0]["code"] == "SOURCE_LAG"
    assert result.metrics["freshness_status"] == "source_lag"
    assert result.metrics["latest_available_trade_dates"] == {"920000.BJ": "2026-07-29"}


async def test_mixed_source_snapshots_coexist_and_repeat_persist_is_idempotent(db_session):
    stock_sh = await seed_stock(db_session, symbol="600519", exchange="SH", name="sh sample")
    stock_bj = await seed_stock(db_session, symbol="920000", exchange="BJ", name="bj sample")
    baostock_record = _daily_record(
        symbol="600519.SH",
        source_code="BAOSTOCK",
        trade_date=date(2026, 7, 30),
    )
    bj_record = _daily_record(
        symbol="920000.BJ",
        source_code="AKSHARE_SINA_DAILY",
        trade_date=date(2026, 7, 30),
    )

    first = await market_data_service.persist_market_data_records(
        db_session,
        stocks=[stock_sh, stock_bj],
        records=[baostock_record, bj_record],
    )
    second = await market_data_service.persist_market_data_records(
        db_session,
        stocks=[stock_sh, stock_bj],
        records=[baostock_record, bj_record],
    )

    snapshots = list((await db_session.execute(select(StockDailySnapshot))).scalars().all())
    assert first["created"] == 2
    assert second["created"] == 0
    assert second["unchanged"] == 2
    assert {(snapshot.stock_id, snapshot.source_code) for snapshot in snapshots} == {
        (stock_sh.id, "BAOSTOCK"),
        (stock_bj.id, "AKSHARE_SINA_DAILY"),
    }
    assert (await db_session.execute(select(func.count()).select_from(AITask))).scalar_one() == 0
    assert (await db_session.execute(select(func.count()).select_from(ResearchTask))).scalar_one() == 0
    assert (await db_session.execute(select(func.count()).select_from(BusinessEvent))).scalar_one() == 0
    assert (await db_session.execute(select(func.count()).select_from(Notification))).scalar_one() == 0


async def test_snapshot_status_uses_source_lag_for_provider_delay():
    record = _daily_record(symbol="600519.SH", source_code="BAOSTOCK", trade_date=date(2026, 7, 29))
    snapshot = market_data_service.snapshot_from_record(stock_id="00000000-0000-0000-0000-000000000001", record=record)

    assert market_data_service.snapshot_status(snapshot, latest_trade_date=date(2026, 7, 30)) == "source_lag"


async def test_akshare_normalization_maps_chinese_fields_and_units(monkeypatch):
    _enable_akshare(monkeypatch)
    provider = AkShareMarketDataProvider(get_settings())

    async def fake_call(_func_name, **_kwargs):
        return FakeFrame(
            [
                {
                    "日期": "2026-07-23",
                    "股票代码": "600519",
                    "开盘": "1680.00",
                    "收盘": "1688.00",
                    "最高": "1699.00",
                    "最低": "1670.00",
                    "成交量": "1000",
                    "成交额": "168800000",
                    "振幅": "1.72",
                    "涨跌幅": "0.48",
                    "涨跌额": "8.00",
                    "换手率": "0.35",
                },
                {
                    "日期": "2026-07-24",
                    "股票代码": "600519",
                    "开盘": "1689.00",
                    "收盘": "1700.00",
                    "最高": "1710.00",
                    "最低": "1685.00",
                    "成交量": "1234",
                    "成交额": "209780000",
                    "振幅": "1.48",
                    "涨跌幅": "0.71",
                    "涨跌额": "12.00",
                    "换手率": "0.41",
                },
            ]
        )

    monkeypatch.setattr(provider, "_call_akshare", fake_call)
    result = await provider.fetch_daily_snapshots(
        MarketDataQuery(
            trade_date=date(2026, 7, 24),
            date_from=date(2026, 7, 24),
            date_to=date(2026, 7, 24),
            symbols=["600519.SH"],
            max_records=1,
            dry_run=True,
        )
    )

    record = result.records[0]
    assert result.status == "pass"
    assert record.symbol == "600519.SH"
    assert record.volume == Decimal("123400")
    assert record.amount == Decimal("209780000")
    assert record.pct_change == Decimal("0.71")
    assert record.turnover_rate == Decimal("0.41")
    assert record.pre_close == Decimal("1688.00")
    assert record.total_market_value is None
    assert "missing_field:pe_ttm" in record.limitations


async def test_market_data_smoke_persist_uses_prefetched_records_once_and_is_idempotent(
    monkeypatch,
    capsys,
    db_session,
):
    _enable_akshare(monkeypatch)
    await create_user(
        db_session,
        username=unique_username("smoke_admin"),
        password="AdminPass123",
        role="admin",
    )
    stock = await seed_stock(db_session, symbol="600519", exchange="SH", name="贵州茅台")
    provider = FakeAkshareSmokeProvider()
    monkeypatch.setattr(market_data_smoke, "get_market_data_provider", lambda *_args: provider)

    first_code = await market_data_smoke.run(
        argparse.Namespace(
            provider="AKSHARE_EASTMONEY",
            symbols="600519.SH",
            date="2026-07-29",
            latest_completed=False,
            max_records=1,
            dry_run=False,
            persist=True,
            cross_check_provider=None,
        )
    )
    first_output = capsys.readouterr().out
    second_code = await market_data_smoke.run(
        argparse.Namespace(
            provider="AKSHARE_EASTMONEY",
            symbols="600519.SH",
            date="2026-07-29",
            latest_completed=False,
            max_records=1,
            dry_run=False,
            persist=True,
            cross_check_provider=None,
        )
    )
    second_output = capsys.readouterr().out

    snapshots = list(
        (await db_session.execute(select(StockDailySnapshot))).scalars().all()
    )
    runs = list(
        (
            await db_session.execute(
                select(MarketDataSyncRun).order_by(MarketDataSyncRun.started_at.asc())
            )
        )
        .scalars()
        .all()
    )
    assert first_code == 0
    assert second_code == 0
    assert provider.fetch_count == 2
    assert provider.calendar_count == 0
    assert len(snapshots) == 1
    assert snapshots[0].stock_id == stock.id
    assert snapshots[0].source_code == "AKSHARE_EASTMONEY"
    assert snapshots[0].volume == Decimal("123400.0000")
    assert snapshots[0].amount == Decimal("209780000.0000")
    assert snapshots[0].pct_change == Decimal("0.710000")
    assert len(runs) == 2
    assert runs[0].status == "complete"
    assert runs[0].created_count == 1
    assert runs[1].status == "complete"
    assert runs[1].created_count == 0
    assert runs[1].unchanged_count == 1
    first_payload = json.loads(first_output)
    first_stages = [event["stage"] for event in first_payload["stage_events"]]
    assert first_stages.index("stock_fetch_succeeded") < first_stages.index("database_transaction_started")
    allowed_stage_fields = {
        "provider_code",
        "symbol",
        "stock_id",
        "trade_date",
        "stage",
        "attempt",
        "duration_ms",
        "sanitized_error_code",
        "sanitized_error_type",
    }
    assert all(set(event) <= allowed_stage_fields for event in first_payload["stage_events"])
    assert "snapshot_upserted" in first_output
    assert '"persist_status": "unchanged"' in second_output
    assert (await db_session.execute(select(func.count()).select_from(AITask))).scalar_one() == 0
    assert (await db_session.execute(select(func.count()).select_from(ResearchTask))).scalar_one() == 0
    assert (await db_session.execute(select(func.count()).select_from(BusinessEvent))).scalar_one() == 0
    assert (await db_session.execute(select(func.count()).select_from(Notification))).scalar_one() == 0


async def test_akshare_retries_retryable_network_errors_three_attempts(monkeypatch):
    _enable_akshare(monkeypatch)
    provider = AkShareMarketDataProvider(get_settings())
    calls = {"count": 0}
    sleeps: list[int | float] = []

    class ProxyError(Exception):
        pass

    def fake_stock_zh_a_hist(**_kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise ProxyError("sanitized")
        return FakeFrame(
            [
                {
                    "日期": "2026-07-29",
                    "股票代码": "600519",
                    "开盘": "1689.00",
                    "收盘": "1700.00",
                    "最高": "1710.00",
                    "最低": "1685.00",
                    "成交量": "1234",
                    "成交额": "209780000",
                    "振幅": "1.48",
                    "涨跌幅": "0.71",
                    "涨跌额": "12.00",
                    "换手率": "0.41",
                },
            ]
        )

    class FakeAkModule:
        stock_zh_a_hist = staticmethod(fake_stock_zh_a_hist)

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(provider, "_load_akshare", lambda: FakeAkModule)
    monkeypatch.setattr("app.providers.market_data.akshare.asyncio.sleep", fake_sleep)

    result = await provider.fetch_daily_snapshots(
        MarketDataQuery(
            trade_date=date(2026, 7, 29),
            date_from=date(2026, 7, 29),
            date_to=date(2026, 7, 29),
            symbols=["600519.SH"],
            max_records=1,
            dry_run=True,
        )
    )

    assert result.status == "pass"
    assert calls["count"] == 3
    assert sleeps == [1, 2]
    assert result.metrics["attempt_counts"]["600519.SH"] == 3
    assert "ProxyError" in str(result.metrics["stage_events"])


async def test_akshare_source_changed_when_required_chinese_columns_missing(monkeypatch):
    _enable_akshare(monkeypatch)
    provider = AkShareMarketDataProvider(get_settings())
    calls = {"count": 0}

    async def fake_call(_func_name, **_kwargs):
        calls["count"] += 1
        return FakeFrame([{"日期": "2026-07-24", "收盘": "10.00"}])

    monkeypatch.setattr(provider, "_call_akshare", fake_call)
    result = await provider.fetch_daily_snapshots(
        MarketDataQuery(
            trade_date=date(2026, 7, 24),
            date_from=date(2026, 7, 24),
            date_to=date(2026, 7, 24),
            symbols=["600519.SH"],
            max_records=1,
            dry_run=True,
        )
    )

    assert result.status == "source_changed"
    assert result.records == []
    assert result.errors[0]["code"] == "MARKET_DATA_SOURCE_CHANGED"
    assert calls["count"] == 1
    assert any(event["stage"] == "normalization_failed" for event in result.metrics["stage_events"])


async def test_latest_completed_trade_day_uses_close_cutoff(monkeypatch):
    _enable_akshare(monkeypatch)

    class CalendarProvider(MockMarketDataProvider):
        async def trade_calendar(self, query: MarketDataQuery):
            del query
            return [
                TradeCalendarDay(trade_date=date(2026, 7, 23), is_open=True),
                TradeCalendarDay(trade_date=date(2026, 7, 24), is_open=True),
            ]

    monkeypatch.setattr(market_data_service, "utc_now", lambda: datetime(2026, 7, 24, 7, 0, tzinfo=UTC))

    resolved = await market_data_service.resolve_trade_date(
        provider=CalendarProvider(),
        mode="latest_completed_trade_day",
        requested_trade_date=None,
        lookback_days=1,
        settings=get_settings(),
    )

    assert resolved == date(2026, 7, 23)


async def test_baostock_explicit_provider_does_not_claim_bj_support(monkeypatch):
    _enable_baostock(monkeypatch)
    provider = BaoStockMarketDataProvider(get_settings())

    result = await provider.fetch_daily_snapshots(
        MarketDataQuery(
            trade_date=date(2026, 7, 24),
            date_from=date(2026, 7, 24),
            date_to=date(2026, 7, 24),
            symbols=["920118.BJ"],
            max_records=1,
            dry_run=True,
        )
    )

    assert result.status == "data_insufficient"
    assert result.records == []
    assert result.errors[0]["code"] == "BAOSTOCK_BJ_UNVERIFIED"


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
