from app.core.config import Settings
from app.providers.market_data.base import MarketDataProvider
from app.providers.market_data.mock import MockMarketDataProvider
from app.providers.market_data.tushare import TushareMarketDataProvider

IMPLEMENTED_MARKET_DATA_PROVIDERS: dict[str, type[MarketDataProvider]] = {
    "TUSHARE_PRO": TushareMarketDataProvider,
    "MOCK_MARKET_DATA": MockMarketDataProvider,
}


def normalize_market_data_source_code(value: str) -> str:
    return value.strip().upper()


def is_market_data_provider_enabled(source_code: str, settings: Settings) -> bool:
    normalized = normalize_market_data_source_code(source_code)
    if normalized == "TUSHARE_PRO":
        return settings.market_data_tushare_enabled
    if normalized == "MOCK_MARKET_DATA":
        return settings.market_data_mock_enabled and not settings.is_production
    return False


def get_market_data_provider(source_code: str, settings: Settings) -> MarketDataProvider | None:
    normalized = normalize_market_data_source_code(source_code)
    provider_class = IMPLEMENTED_MARKET_DATA_PROVIDERS.get(normalized)
    if not provider_class:
        return None
    return provider_class(settings) if normalized == "TUSHARE_PRO" else provider_class()


def market_data_provider_catalog(settings: Settings) -> list[dict[str, object]]:
    return [
        {
            "source_code": "TUSHARE_PRO",
            "display_name": "Tushare Pro",
            "implemented": True,
            "enabled_by_config": settings.market_data_tushare_enabled,
            "source_type": "third_party_data_service",
            "authorization_status": "unverified",
            "usage_scope": ["local_development", "internal_testing"],
            "production_enabled": False,
            "capabilities": ["daily_snapshot", "trade_calendar"],
            "limitations": ["开发验证候选；公开展示、再分发和生产商用授权尚未确认。"],
        },
        {
            "source_code": "MOCK_MARKET_DATA",
            "display_name": "测试用 Mock 行情",
            "implemented": True,
            "enabled_by_config": settings.market_data_mock_enabled and not settings.is_production,
            "source_type": "development_mock",
            "authorization_status": "prohibited",
            "usage_scope": ["local_development"],
            "production_enabled": False,
            "capabilities": ["daily_snapshot", "trade_calendar"],
            "limitations": ["仅用于自动测试；不得在产品页面伪装为真实行情。"],
        },
    ]
