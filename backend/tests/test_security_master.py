from datetime import date

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.time import utc_now
from app.models.security_master import SecurityMasterSyncRun
from app.models.stock import Stock
from app.providers.securities.baostock import BaoStockSecurityMasterProvider
from app.providers.securities.bse import BseSecurityMasterProvider
from app.providers.securities.models import (
    SecurityMasterCapability,
    SecurityMasterQuery,
    SecurityMasterRecord,
    SecurityMasterResult,
)
from app.providers.securities.sse import SseSecurityMasterProvider
from app.providers.securities.szse import SzseSecurityMasterProvider
from app.providers.statuses import ProviderStatus
from app.services import security_master as security_master_service
from app.services.security_master import get_security_master_status, start_security_master_sync
from tests.conftest import create_user, login, unique_username


def _settings():
    return get_settings()


def _record(
    *,
    source_code: str = "SSE_SECURITY_MASTER",
    code: str = "600519",
    exchange: str = "SH",
    short_name: str = "贵州茅台",
    full_name: str = "贵州茅台股份有限公司",
    board: str = "main_board",
    listing_status: str = "active",
    pinyin: str = "guizhoumaotai",
    pinyin_initials: str = "gzmt",
    raw_hash: str = "hash-600519-v1",
    previous_symbols: list[str] | None = None,
) -> SecurityMasterRecord:
    from app.core.time import utc_now

    return SecurityMasterRecord(
        source_code=source_code,
        provider_security_id=f"{source_code}:{code}",
        symbol=f"{code}.{exchange}",
        code=code,
        exchange=exchange,
        market="A_SHARE",
        board=board,
        security_type="common_stock",
        short_name=short_name,
        full_name=full_name,
        english_name=None,
        listing_status=listing_status,
        listed_at=date(2001, 8, 27),
        delisted_at=None,
        previous_symbols=previous_symbols or [],
        aliases=[short_name, full_name, f"{short_name}旧名"],
        raw_metadata_hash=raw_hash,
        fetched_at=utc_now(),
        data_completeness="complete",
        missing_fields=[],
        pinyin=pinyin,
        pinyin_initials=pinyin_initials,
    )


class StaticProvider:
    source_code = "SSE_SECURITY_MASTER"

    def __init__(self, result: SecurityMasterResult) -> None:
        self.result = result

    def capabilities(self) -> list[SecurityMasterCapability]:
        return [
            SecurityMasterCapability(
                name="security_master",
                description="test provider",
                supports_pagination=False,
            )
        ]

    async def health_check(self) -> SecurityMasterResult:
        return self.result

    async def list_securities(self, query: SecurityMasterQuery) -> SecurityMasterResult:
        return SecurityMasterResult(
            status=self.result.status,
            records=self.result.records[: query.max_records],
            errors=self.result.errors,
            metrics=self.result.metrics,
            provider_metadata=self.result.provider_metadata,
            request_count=self.result.request_count,
            success_count=self.result.success_count,
            failure_count=self.result.failure_count,
        )

    def normalize(self, raw_record: dict) -> SecurityMasterRecord:
        raise NotImplementedError


def _enable_security_master(monkeypatch, *, source: str = "SSE_SECURITY_MASTER"):
    monkeypatch.setenv("SECURITY_MASTER_SYNC_ENABLED", "true")
    monkeypatch.setenv("SECURITY_MASTER_REAL_NETWORK_ENABLED", "true")
    if source == "SSE_SECURITY_MASTER":
        monkeypatch.setenv("SECURITY_MASTER_SSE_ENABLED", "true")
    if source == "SZSE_SECURITY_MASTER":
        monkeypatch.setenv("SECURITY_MASTER_SZSE_ENABLED", "true")
    if source == "BSE_SECURITY_MASTER":
        monkeypatch.setenv("SECURITY_MASTER_BSE_ENABLED", "true")
    if source in {"BAOSTOCK_SECURITY_MASTER", "BAOSTOCK_DEVELOPMENT_FALLBACK"}:
        monkeypatch.setenv("SECURITY_MASTER_BAOSTOCK_ENABLED", "true")
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_security_provider_sample_normalization():
    sse = SseSecurityMasterProvider(_settings()).normalize(
        {
            "SECURITY_CODE_A": "688981",
            "SECURITY_ABBR_A": "中芯国际",
            "COMPANY_FULL_NAME": "中芯国际集成电路制造有限公司",
            "LISTING_DATE": "20200716",
            "LIST_STATUS": "上市",
        }
    )
    assert sse.symbol == "688981.SH"
    assert sse.exchange == "SH"
    assert sse.board == "star_board"
    assert sse.security_type == "common_stock"
    assert sse.listing_status == "active"

    szse = SzseSecurityMasterProvider(_settings()).normalize(
        {
            "agdm": "300750",
            "agjc": "宁德时代",
            "gsmc": "宁德时代新能源科技股份有限公司",
            "agssrq": "2018-06-11",
            "zt": "上市",
        }
    )
    assert szse.symbol == "300750.SZ"
    assert szse.board == "chinext"
    assert szse.listing_status == "active"

    bse = BseSecurityMasterProvider(_settings()).normalize(
        {
            "code": "835185",
            "name": "贝特瑞",
            "full_name": "贝特瑞新材料集团股份有限公司",
            "exchange": "BJ",
            "status": "上市",
        }
    )
    assert bse.symbol == "835185.BJ"
    assert bse.board == "bse"

    baostock = BaoStockSecurityMasterProvider(_settings()).normalize(
        {"code": "sz.000001", "code_name": "平安银行", "ipoDate": "1991-04-03", "tradeStatus": "1"}
    )
    assert baostock.symbol == "000001.SZ"
    assert baostock.exchange == "SZ"


@pytest.mark.asyncio
async def test_security_master_sync_upserts_seed_and_keeps_stock_id(monkeypatch, db_session):
    _enable_security_master(monkeypatch)
    monkeypatch.setitem(
        security_master_service.COMPLETENESS_RULES,
        "SSE_SECURITY_MASTER",
        {"min_board_counts": {"main_board": 1, "star_board": 1}, "probe_symbols": {"600519.SH", "688981.SH"}},
    )
    admin = await create_user(db_session, username=unique_username("sec_admin"), password="AdminPass123", role="admin")
    seed = Stock(
        symbol="600519.SH",
        code="600519",
        exchange="SH",
        name="贵州茅台",
        market="A_SHARE",
        board="main_board",
        security_type="common_stock",
        short_name="贵州茅台",
        full_name="贵州茅台",
        listing_status="active",
        aliases=["贵州茅台"],
        pinyin="guizhoumaotai",
        pinyin_initials="gzmt",
        source_code="development_seed",
        source_record_id="600519.SH",
        data_completeness="partial",
        is_searchable=True,
        list_status="listed",
        currency="CNY",
        data_source="development_seed",
    )
    db_session.add(seed)
    await db_session.commit()
    await db_session.refresh(seed)

    provider = StaticProvider(
        SecurityMasterResult(
            status=ProviderStatus.PASS,
            records=[
                _record(raw_hash="hash-600519-v2"),
                _record(
                    source_code="SSE_SECURITY_MASTER",
                    code="688981",
                    exchange="SH",
                    short_name="中芯国际",
                    full_name="中芯国际集成电路制造有限公司",
                    board="star_board",
                    pinyin="zhongxinguoji",
                    pinyin_initials="zxgj",
                    raw_hash="hash-688981-v1",
                ),
            ],
            request_count=1,
            success_count=1,
        )
    )
    monkeypatch.setattr("app.services.security_master.get_security_master_provider", lambda *_args: provider)
    monkeypatch.setattr("app.services.security_master.is_security_master_provider_enabled", lambda *_args: True)

    run = await start_security_master_sync(
        db_session,
        admin_user=admin,
        source_code="SSE_SECURITY_MASTER",
        exchanges=["SH"],
        force=False,
        settings=get_settings(),
        request_id="test-security-master",
    )

    assert run.status == "complete"
    assert run.received_count == 2
    assert run.created_count == 1
    assert run.updated_count == 1

    stocks = (await db_session.execute(select(Stock).order_by(Stock.symbol))).scalars().all()
    assert len(stocks) == 2
    refreshed_seed = (await db_session.execute(select(Stock).where(Stock.symbol == "600519.SH"))).scalar_one()
    assert refreshed_seed.id == seed.id
    assert refreshed_seed.source_code == "SSE_SECURITY_MASTER"
    assert refreshed_seed.data_source == "development_seed"
    assert refreshed_seed.data_completeness == "complete"
    status = await get_security_master_status(db_session)
    assert status.development_seed_count == 0
    assert status.seed_covered_count == 1

    second = await start_security_master_sync(
        db_session,
        admin_user=admin,
        source_code="SSE_SECURITY_MASTER",
        exchanges=["SH"],
        force=False,
        settings=get_settings(),
        request_id="test-security-master-2",
    )
    assert second.status == "complete"
    assert second.created_count == 0
    assert second.unchanged_count == 2


@pytest.mark.asyncio
async def test_security_master_sync_keeps_existing_stocks_on_network_failure(monkeypatch, db_session):
    _enable_security_master(monkeypatch)
    admin = await create_user(db_session, username=unique_username("sec_fail"), password="AdminPass123", role="admin")
    stock = _record()
    provider = StaticProvider(
        SecurityMasterResult(
            status=ProviderStatus.NETWORK_ERROR,
            errors=[{"code": "NETWORK_ERROR", "summary": "temporary failure"}],
            request_count=1,
            failure_count=1,
        )
    )
    monkeypatch.setattr("app.services.security_master.get_security_master_provider", lambda *_args: provider)
    monkeypatch.setattr("app.services.security_master.is_security_master_provider_enabled", lambda *_args: True)

    db_session.add(
        Stock(
            symbol=stock.symbol,
            code=stock.code,
            exchange=stock.exchange,
            name=stock.short_name,
            market=stock.market,
            board=stock.board,
            security_type=stock.security_type,
            short_name=stock.short_name,
            full_name=stock.full_name,
            listing_status=stock.listing_status,
            aliases=stock.aliases,
            pinyin=stock.pinyin,
            pinyin_initials=stock.pinyin_initials,
            source_code="development_seed",
            source_record_id=stock.symbol,
            data_completeness="partial",
            is_searchable=True,
            list_status="listed",
            currency="CNY",
            data_source="development_seed",
        )
    )
    await db_session.commit()

    run = await start_security_master_sync(
        db_session,
        admin_user=admin,
        source_code="SSE_SECURITY_MASTER",
        exchanges=["SH"],
        force=False,
        settings=get_settings(),
        request_id="test-network-failure",
    )

    assert run.status == "network_error"
    assert run.failure_count == 1
    assert (await db_session.execute(select(Stock))).scalars().all()


@pytest.mark.asyncio
async def test_sse_completeness_gate_marks_small_sample_as_data_insufficient(monkeypatch, db_session):
    _enable_security_master(monkeypatch)
    admin = await create_user(db_session, username=unique_username("sec_gate"), password="AdminPass123", role="admin")
    provider = StaticProvider(
        SecurityMasterResult(
            status=ProviderStatus.PASS,
            records=[
                _record(code="600000", short_name="SSE A", full_name="SSE A", raw_hash="hash-600000"),
                _record(code="600004", short_name="SSE B", full_name="SSE B", raw_hash="hash-600004"),
                _record(code="600006", short_name="SSE C", full_name="SSE C", raw_hash="hash-600006"),
            ],
            request_count=1,
            success_count=1,
        )
    )
    monkeypatch.setattr("app.services.security_master.get_security_master_provider", lambda *_args: provider)
    monkeypatch.setattr("app.services.security_master.is_security_master_provider_enabled", lambda *_args: True)

    run = await start_security_master_sync(
        db_session,
        admin_user=admin,
        source_code="SSE_SECURITY_MASTER",
        exchanges=["SH"],
        force=False,
        settings=get_settings(),
        request_id="test-sse-gate",
    )

    assert run.status == "data_insufficient"
    assert run.received_count == 3
    assert run.metrics["completeness_gate"]["passed"] is False
    assert "probe_missing:600519.SH" in run.metrics["completeness_gate"]["missing"]


@pytest.mark.asyncio
async def test_szse_network_error_does_not_clear_existing_stocks(monkeypatch, db_session):
    _enable_security_master(monkeypatch, source="SZSE_SECURITY_MASTER")
    admin = await create_user(db_session, username=unique_username("sec_szse"), password="AdminPass123", role="admin")
    db_session.add(
        Stock(
            symbol="300750.SZ",
            code="300750",
            exchange="SZ",
            name="CATL",
            market="A_SHARE",
            board="chinext",
            security_type="common_stock",
            short_name="CATL",
            full_name="CATL",
            listing_status="active",
            aliases=["CATL"],
            source_code="development_seed",
            source_record_id="300750.SZ",
            data_completeness="partial",
            is_searchable=True,
            list_status="listed",
            currency="CNY",
            data_source="development_seed",
        )
    )
    await db_session.commit()
    provider = StaticProvider(
        SecurityMasterResult(
            status=ProviderStatus.NETWORK_ERROR,
            errors=[{"code": "500", "summary": "SZSE returned HTML error page"}],
            request_count=1,
            failure_count=1,
        )
    )
    monkeypatch.setattr("app.services.security_master.get_security_master_provider", lambda *_args: provider)
    monkeypatch.setattr("app.services.security_master.is_security_master_provider_enabled", lambda *_args: True)

    run = await start_security_master_sync(
        db_session,
        admin_user=admin,
        source_code="SZSE_SECURITY_MASTER",
        exchanges=["SZ"],
        force=False,
        settings=get_settings(),
        request_id="test-szse-500",
    )

    assert run.status == "network_error"
    assert (await db_session.execute(select(func.count()).select_from(Stock))).scalar_one() == 1


@pytest.mark.asyncio
async def test_bse_current_920_and_previous_code_keep_same_stock_id(monkeypatch, client, db_session):
    _enable_security_master(monkeypatch, source="BSE_SECURITY_MASTER")
    monkeypatch.setattr("app.services.security_master.is_security_master_provider_enabled", lambda *_args: True)
    admin = await create_user(db_session, username=unique_username("sec_bse"), password="AdminPass123", role="admin")
    user = await create_user(db_session, username=unique_username("sec_bse_user"), password="UserPass123")
    old = Stock(
        symbol="835438.BJ",
        code="835438",
        exchange="BJ",
        name="OldBSE",
        market="A_SHARE",
        board="bse",
        security_type="common_stock",
        short_name="OldBSE",
        full_name="OldBSE",
        listing_status="active",
        aliases=["835438", "835438.BJ"],
        source_code="development_seed",
        source_record_id="835438.BJ",
        data_completeness="partial",
        is_searchable=True,
        list_status="listed",
        currency="CNY",
        data_source="development_seed",
    )
    db_session.add(old)
    await db_session.commit()
    await db_session.refresh(old)
    provider = StaticProvider(
        SecurityMasterResult(
            status=ProviderStatus.PASS,
            records=[
                _record(
                    source_code="BSE_SECURITY_MASTER",
                    code="920438",
                    exchange="BJ",
                    short_name="BSECurrent",
                    full_name="BSECurrent Corp",
                    board="bse",
                    raw_hash="hash-920438",
                    previous_symbols=["835438.BJ", "835438"],
                )
            ],
            request_count=1,
            success_count=1,
        )
    )
    monkeypatch.setattr("app.services.security_master.get_security_master_provider", lambda *_args: provider)

    run = await start_security_master_sync(
        db_session,
        admin_user=admin,
        source_code="BSE_SECURITY_MASTER",
        exchanges=["BJ"],
        force=False,
        settings=get_settings(),
        request_id="test-bse-code-map",
    )

    assert run.status == "complete"
    refreshed = (await db_session.execute(select(Stock).where(Stock.id == old.id))).scalar_one()
    assert refreshed.symbol == "920438.BJ"
    assert refreshed.code == "920438"
    assert "835438.BJ" in refreshed.aliases

    await login(client, username=user.username, password="UserPass123")
    current = await client.get("/api/v1/stocks/search", params={"q": "920438"})
    previous = await client.get("/api/v1/stocks/search", params={"q": "835438"})
    assert current.json()["data"]["items"][0]["id"] == str(old.id)
    assert previous.json()["data"]["items"][0]["id"] == str(old.id)


@pytest.mark.asyncio
async def test_baostock_development_fallback_does_not_overwrite_official(monkeypatch, db_session):
    _enable_security_master(monkeypatch, source="BAOSTOCK_DEVELOPMENT_FALLBACK")
    monkeypatch.setattr(
        "app.services.security_master.is_security_master_provider_enabled",
        lambda source_code, settings: source_code == "BAOSTOCK_DEVELOPMENT_FALLBACK",
    )
    admin = await create_user(db_session, username=unique_username("sec_bao"), password="AdminPass123", role="admin")
    official = Stock(
        symbol="600519.SH",
        code="600519",
        exchange="SH",
        name="OfficialName",
        market="A_SHARE",
        board="main_board",
        security_type="common_stock",
        short_name="OfficialName",
        full_name="OfficialName Corp",
        listing_status="active",
        aliases=["OfficialName"],
        source_code="SSE_SECURITY_MASTER",
        source_record_id="600519",
        data_completeness="complete",
        is_searchable=True,
        list_status="listed",
        currency="CNY",
        data_source="SSE_SECURITY_MASTER",
    )
    db_session.add(official)
    await db_session.commit()
    provider = StaticProvider(
        SecurityMasterResult(
            status=ProviderStatus.PASS,
            records=[
                _record(
                    source_code="BAOSTOCK_DEVELOPMENT_FALLBACK",
                    code="600519",
                    exchange="SH",
                    short_name="FallbackName",
                    full_name="FallbackName Corp",
                    board="star_board",
                    raw_hash="hash-baostock-600519",
                )
            ],
            request_count=1,
            success_count=1,
        )
    )
    monkeypatch.setattr("app.services.security_master.get_security_master_provider", lambda *_args: provider)

    run = await start_security_master_sync(
        db_session,
        admin_user=admin,
        source_code="BAOSTOCK_SECURITY_MASTER",
        exchanges=["SH"],
        force=False,
        settings=get_settings(),
        request_id="test-baostock-priority",
    )

    refreshed = (await db_session.execute(select(Stock).where(Stock.symbol == "600519.SH"))).scalar_one()
    assert run.status == "data_insufficient"
    assert run.metrics["merge_conflict_count"] > 0
    assert refreshed.source_code == "SSE_SECURITY_MASTER"
    assert refreshed.short_name == "OfficialName"
    assert "FallbackName" in refreshed.aliases


@pytest.mark.asyncio
async def test_baostock_development_fallback_blocked_outside_development(monkeypatch, client, db_session):
    _enable_security_master(monkeypatch, source="BAOSTOCK_DEVELOPMENT_FALLBACK")
    monkeypatch.setenv("APP_ENV", "staging")
    get_settings.cache_clear()
    admin = await create_user(db_session, username=unique_username("sec_bao_env"), password="AdminPass123", role="admin")
    await login(client, username=admin.username, password="AdminPass123")

    response = await client.post(
        "/api/v1/admin/security-master/sync",
        json={"source_code": "BAOSTOCK_DEVELOPMENT_FALLBACK"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SECURITY_MASTER_REAL_NETWORK_DISABLED"


@pytest.mark.asyncio
async def test_stock_search_matches_code_symbol_name_full_name_pinyin_alias_and_filters(client, db_session):
    user = await create_user(db_session, username=unique_username("stock_search"), password="UserPass123")
    active = Stock(
        symbol="600519.SH",
        code="600519",
        exchange="SH",
        name="贵州茅台",
        market="A_SHARE",
        board="main_board",
        security_type="common_stock",
        short_name="贵州茅台",
        full_name="贵州茅台股份有限公司",
        listing_status="active",
        aliases=["贵州茅台旧名"],
        pinyin="guizhoumaotai",
        pinyin_initials="gzmt",
        source_code="SSE_SECURITY_MASTER",
        source_record_id="600519",
        data_completeness="complete",
        is_searchable=True,
        list_status="listed",
        currency="CNY",
        data_source="SSE_SECURITY_MASTER",
    )
    suspended = Stock(
        symbol="300750.SZ",
        code="300750",
        exchange="SZ",
        name="宁德时代",
        market="A_SHARE",
        board="chinext",
        security_type="common_stock",
        short_name="宁德时代",
        full_name="宁德时代新能源科技股份有限公司",
        listing_status="suspended",
        aliases=[],
        pinyin="ningdeshidai",
        pinyin_initials="ndsd",
        source_code="SZSE_SECURITY_MASTER",
        source_record_id="300750",
        data_completeness="complete",
        is_searchable=True,
        list_status="listed",
        currency="CNY",
        data_source="SZSE_SECURITY_MASTER",
    )
    unsupported = Stock(
        symbol="510300.SH",
        code="510300",
        exchange="SH",
        name="沪深300ETF",
        market="A_SHARE",
        board="main_board",
        security_type="etf",
        short_name="沪深300ETF",
        full_name="沪深300交易型开放式指数证券投资基金",
        listing_status="active",
        aliases=[],
        source_code="SSE_SECURITY_MASTER",
        source_record_id="510300",
        data_completeness="complete",
        is_searchable=True,
        list_status="listed",
        currency="CNY",
        data_source="SSE_SECURITY_MASTER",
    )
    delisted = Stock(
        symbol="000001.SZ",
        code="000001",
        exchange="SZ",
        name="平安银行",
        market="A_SHARE",
        board="main_board",
        security_type="common_stock",
        short_name="平安银行",
        full_name="平安银行股份有限公司",
        listing_status="delisted",
        aliases=[],
        pinyin="pinganyinhang",
        pinyin_initials="payh",
        source_code="SZSE_SECURITY_MASTER",
        source_record_id="000001",
        data_completeness="complete",
        is_searchable=False,
        list_status="delisted",
        currency="CNY",
        data_source="SZSE_SECURITY_MASTER",
    )
    db_session.add_all([active, suspended, unsupported, delisted])
    await db_session.commit()
    await login(client, username=user.username, password="UserPass123")

    assert (await client.get("/api/v1/stocks/search")).json()["data"]["total"] == 0
    code = await client.get("/api/v1/stocks/search", params={"q": "600519"})
    assert code.status_code == 200
    assert code.json()["data"]["items"][0]["id"] == str(active.id)
    symbol = await client.get("/api/v1/stocks/search", params={"q": "600519.SH"})
    assert symbol.json()["data"]["items"][0]["id"] == str(active.id)
    name = await client.get("/api/v1/stocks/search", params={"q": "贵州茅台"})
    assert name.json()["data"]["items"][0]["id"] == str(active.id)
    full_name = await client.get("/api/v1/stocks/search", params={"q": "新能源科技"})
    assert full_name.json()["data"]["items"][0]["id"] == str(suspended.id)
    pinyin = await client.get("/api/v1/stocks/search", params={"q": "guizhoumaotai"})
    assert pinyin.json()["data"]["items"][0]["id"] == str(active.id)
    initials = await client.get("/api/v1/stocks/search", params={"q": "ndsd"})
    assert initials.json()["data"]["items"][0]["id"] == str(suspended.id)
    alias = await client.get("/api/v1/stocks/search", params={"q": "贵州茅台旧名"})
    assert alias.json()["data"]["items"][0]["id"] == str(active.id)
    etf = await client.get("/api/v1/stocks/search", params={"q": "510300"})
    assert etf.json()["data"]["total"] == 0
    hidden = await client.get("/api/v1/stocks/search", params={"q": "000001"})
    assert hidden.json()["data"]["total"] == 0
    filtered = await client.get("/api/v1/stocks/search", params={"q": "宁德", "board": "chinext"})
    assert filtered.json()["data"]["total"] == 1


@pytest.mark.asyncio
async def test_security_master_admin_api_permissions_and_csrf(monkeypatch, client, db_session):
    _enable_security_master(monkeypatch)
    user = await create_user(db_session, username=unique_username("sec_user"), password="UserPass123")
    await login(client, username=user.username, password="UserPass123")
    forbidden = await client.post("/api/v1/admin/security-master/sync", json={"source_code": "SSE_SECURITY_MASTER"})
    assert forbidden.status_code == 403

    admin = await create_user(db_session, username=unique_username("sec_admin_api"), password="AdminPass123", role="admin")
    await login(client, username=admin.username, password="AdminPass123")
    client.headers.pop("X-CSRF-Token", None)
    missing_csrf = await client.post("/api/v1/admin/security-master/sync", json={"source_code": "SSE_SECURITY_MASTER"})
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["error"]["code"] == "CSRF_TOKEN_REQUIRED"

    csrf_token = client.cookies.get("geniustrader_csrf")
    client.headers["X-CSRF-Token"] = csrf_token or ""
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    blocked = await client.post("/api/v1/admin/security-master/sync", json={"source_code": "SSE_SECURITY_MASTER"})
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "SECURITY_MASTER_REAL_NETWORK_DISABLED"


@pytest.mark.asyncio
async def test_watchlist_rejects_unsearchable_stock_and_keeps_user_isolation(client, db_session):
    user = await create_user(db_session, username=unique_username("wl_real"), password="UserPass123")
    other = await create_user(db_session, username=unique_username("wl_other"), password="UserPass123")
    stock = Stock(
        symbol="600519.SH",
        code="600519",
        exchange="SH",
        name="贵州茅台",
        market="A_SHARE",
        board="main_board",
        security_type="common_stock",
        short_name="贵州茅台",
        full_name="贵州茅台股份有限公司",
        listing_status="active",
        aliases=[],
        pinyin="guizhoumaotai",
        pinyin_initials="gzmt",
        source_code="SSE_SECURITY_MASTER",
        source_record_id="600519",
        data_completeness="complete",
        is_searchable=True,
        list_status="listed",
        currency="CNY",
        data_source="SSE_SECURITY_MASTER",
    )
    hidden = Stock(
        symbol="000001.SZ",
        code="000001",
        exchange="SZ",
        name="平安银行",
        market="A_SHARE",
        board="main_board",
        security_type="common_stock",
        short_name="平安银行",
        full_name="平安银行股份有限公司",
        listing_status="delisted",
        aliases=[],
        source_code="SZSE_SECURITY_MASTER",
        source_record_id="000001",
        data_completeness="complete",
        is_searchable=False,
        list_status="delisted",
        currency="CNY",
        data_source="SZSE_SECURITY_MASTER",
    )
    db_session.add_all([stock, hidden])
    await db_session.commit()
    await db_session.refresh(stock)
    await db_session.refresh(hidden)

    await login(client, username=user.username, password="UserPass123")
    group = (await client.post("/api/v1/watchlist/groups", json={"name": "真实自选"})).json()["data"]
    tag = (await client.post("/api/v1/watchlist/tags", json={"name": "核心观察"})).json()["data"]
    added = await client.post(
        "/api/v1/watchlist",
        json={
            "stock_id": str(stock.id),
            "group_id": group["id"],
            "tag_ids": [tag["id"]],
            "attention_reason": "跟踪公告与经营变化",
        },
    )
    assert added.status_code == 201
    duplicate = await client.post("/api/v1/watchlist", json={"stock_id": str(stock.id)})
    assert duplicate.status_code == 201
    assert duplicate.json()["data"]["id"] == added.json()["data"]["id"]
    patched = await client.patch(
        f"/api/v1/watchlist/{added.json()['data']['id']}",
        json={"attention_reason": "更新后的关注原因", "tag_ids": []},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["attention_reason"] == "更新后的关注原因"
    rejected = await client.post("/api/v1/watchlist", json={"stock_id": str(hidden.id)})
    assert rejected.status_code == 404

    await login(client, username=other.username, password="UserPass123")
    isolated = await client.get("/api/v1/watchlist")
    assert isolated.status_code == 200
    assert isolated.json()["data"]["total"] == 0
    other_get = await client.get(f"/api/v1/watchlist/{added.json()['data']['id']}")
    assert other_get.status_code == 404


@pytest.mark.asyncio
async def test_security_master_status_reports_seed_only_gap(client, db_session):
    user = await create_user(db_session, username=unique_username("sec_status"), password="UserPass123")
    db_session.add(
        Stock(
            symbol="600519.SH",
            code="600519",
            exchange="SH",
            name="贵州茅台",
            market="A_SHARE",
            board="main_board",
            security_type="common_stock",
            short_name="贵州茅台",
            full_name="贵州茅台",
            listing_status="active",
            aliases=[],
            source_code="development_seed",
            source_record_id="600519.SH",
            data_completeness="partial",
            is_searchable=True,
            list_status="listed",
            currency="CNY",
            data_source="development_seed",
        )
    )
    await db_session.commit()
    await login(client, username=user.username, password="UserPass123")

    status = await client.get("/api/v1/security-master/status")

    assert status.status_code == 200
    data = status.json()["data"]
    assert data["total_count"] == 1
    assert data["development_seed_count"] == 1
    assert data["data_gaps"]
    assert data["latest_sync_run"] is None


@pytest.mark.asyncio
async def test_running_security_master_sync_is_rejected(monkeypatch, client, db_session):
    _enable_security_master(monkeypatch)
    admin = await create_user(db_session, username=unique_username("sec_running"), password="AdminPass123", role="admin")
    db_session.add(
        SecurityMasterSyncRun(
            triggered_by_user_id=admin.id,
            source_code="SSE_SECURITY_MASTER",
            status="running",
            exchanges=["SH"],
            request_count=0,
            received_count=0,
            created_count=0,
            updated_count=0,
            unchanged_count=0,
            deactivated_count=0,
            failure_count=0,
            started_at=utc_now(),
            metrics={},
        )
    )
    await db_session.commit()
    await login(client, username=admin.username, password="AdminPass123")

    response = await client.post("/api/v1/admin/security-master/sync", json={"source_code": "SSE_SECURITY_MASTER"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SECURITY_MASTER_SYNC_ALREADY_RUNNING"
