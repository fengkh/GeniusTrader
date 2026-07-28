import argparse

import pytest
from cryptography.fernet import Fernet

from app.cli.market_data_provider_smoke import run as run_market_data_smoke
from app.core.config import Settings, get_settings
from app.core.release_gate import (
    private_beta_feature_matrix,
    production_settings_checks,
    validate_production_startup_settings,
)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _production_settings(**overrides):
    values = {
        "database_url": "postgresql+psycopg://geniustrader:StrongSecret123@postgres:5432/geniustrader",
        "app_env": "production",
        "debug": False,
        "app_encryption_keys": Fernet.generate_key().decode("ascii"),
        "session_cookie_secure": True,
        "cors_allowed_origins": "https://example.com",
        "trusted_hosts": "example.com",
        "public_registration_enabled": False,
        "market_data_provider_enabled": False,
        "market_data_sync_enabled": False,
        "market_data_real_network_enabled": False,
        "market_data_tushare_enabled": False,
        "market_data_mock_enabled": False,
        "announcement_bse_enabled": False,
        "security_master_baostock_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)


def _codes(settings: Settings) -> set[str]:
    return {item.code for item in production_settings_checks(settings) if item.status == "fail"}


def test_production_release_gate_fails_missing_encryption_key():
    settings = _production_settings(app_encryption_keys="")

    assert "APP_ENCRYPTION_KEYS_MISSING" in _codes(settings)
    with pytest.raises(RuntimeError):
        validate_production_startup_settings(settings)


def test_production_release_gate_fails_wildcard_cors_and_trusted_hosts():
    settings = _production_settings(cors_allowed_origins="*", trusted_hosts="*")

    codes = _codes(settings)
    assert "CORS_WILDCARD" in codes
    assert "TRUSTED_HOSTS_WILDCARD" in codes


def test_production_release_gate_fails_insecure_cookie_and_public_registration():
    settings = _production_settings(session_cookie_secure=False, public_registration_enabled=True)

    codes = _codes(settings)
    assert "SESSION_COOKIE_INSECURE" in codes
    assert "PUBLIC_REGISTRATION_ENABLED" in codes


def test_production_release_gate_fails_unauthorized_market_provider():
    settings = _production_settings(
        market_data_provider_enabled=True,
        market_data_real_network_enabled=True,
        market_data_tushare_enabled=True,
        market_data_tushare_authorization_status="unverified",
    )

    assert "UNAUTHORIZED_MARKET_PROVIDER_ENABLED" in _codes(settings)


def test_production_release_gate_allows_market_provider_closed_without_token():
    settings = _production_settings(market_data_tushare_token="", market_data_tushare_authorization_status="unverified")

    codes = _codes(settings)
    assert "UNAUTHORIZED_MARKET_PROVIDER_ENABLED" not in codes
    validate_production_startup_settings(settings)


def test_production_release_gate_blocks_bse_and_baostock_enabled():
    settings = _production_settings(announcement_bse_enabled=True, security_master_baostock_enabled=True)

    codes = _codes(settings)
    assert "BSE_DISCLOSURE_ENABLED_IN_PRODUCTION" in codes
    assert "BAOSTOCK_ENABLED_IN_PRODUCTION" in codes


def test_private_beta_feature_matrix_closes_non_mvp_features():
    matrix = {item["feature"]: item for item in private_beta_feature_matrix(_production_settings())}

    assert matrix["WATCHLIST"]["enabled"] is True
    assert matrix["USER_AI_BYOK"]["enabled"] is True
    assert matrix["DAILY_REVIEWS"]["enabled"] is True
    assert matrix["MARKET_DATA"]["enabled"] is False
    assert matrix["PUBLIC_REGISTRATION"]["enabled"] is False
    assert matrix["AUTO_TRADING"]["enabled"] is False
    assert matrix["SOCIAL_CRAWLING"]["enabled"] is False


@pytest.mark.asyncio
async def test_market_data_provider_smoke_no_token_exits_3_without_leak(monkeypatch, capsys):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("MARKET_DATA_TUSHARE_TOKEN", "")
    get_settings.cache_clear()

    code = await run_market_data_smoke(
        argparse.Namespace(
            provider="TUSHARE_PRO",
            symbols="600519.SH,000001.SZ",
            date="2026-07-24",
            max_records=2,
            dry_run=True,
            persist=False,
        )
    )

    output = capsys.readouterr().out
    assert code == 3
    assert "MARKET_DATA_PROVIDER_NOT_CONFIGURED" in output
    assert "not_configured" in output
    assert "APP_ENCRYPTION_KEYS" not in output


@pytest.mark.asyncio
async def test_market_data_provider_smoke_blocks_production_persist_without_authorization(monkeypatch, capsys):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("MARKET_DATA_TUSHARE_TOKEN", "secret-token-not-printed")
    monkeypatch.setenv("MARKET_DATA_TUSHARE_AUTHORIZATION_STATUS", "unverified")
    get_settings.cache_clear()

    code = await run_market_data_smoke(
        argparse.Namespace(
            provider="TUSHARE_PRO",
            symbols="600519.SH",
            date="2026-07-24",
            max_records=1,
            dry_run=True,
            persist=True,
        )
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "MARKET_DATA_PERMISSION_DENIED" in output
    assert "secret-token-not-printed" not in output
