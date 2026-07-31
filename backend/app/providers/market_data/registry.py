from app.core.config import Settings
from app.providers.market_data.akshare import AkShareMarketDataProvider
from app.providers.market_data.akshare_sina import AkShareSinaDailyMarketDataProvider
from app.providers.market_data.baostock import BaoStockMarketDataProvider
from app.providers.market_data.base import MarketDataProvider
from app.providers.market_data.mock import MockMarketDataProvider
from app.providers.market_data.tushare import TushareMarketDataProvider

IMPLEMENTED_MARKET_DATA_PROVIDERS: dict[str, type[MarketDataProvider]] = {
    "AKSHARE_EASTMONEY": AkShareMarketDataProvider,
    "AKSHARE_SINA_DAILY": AkShareSinaDailyMarketDataProvider,
    "BAOSTOCK": BaoStockMarketDataProvider,
    "TUSHARE_PRO": TushareMarketDataProvider,
    "MOCK_MARKET_DATA": MockMarketDataProvider,
}

TRIAL_ROUTE_BY_EXCHANGE = {
    "SH": "BAOSTOCK",
    "SZ": "BAOSTOCK",
    "BJ": "AKSHARE_SINA_DAILY",
}


def normalize_market_data_source_code(value: str) -> str:
    return value.strip().upper()


def is_market_data_provider_enabled(source_code: str, settings: Settings) -> bool:
    normalized = normalize_market_data_source_code(source_code)
    if normalized in {"AKSHARE_EASTMONEY", "AKSHARE_SINA_DAILY", "BAOSTOCK", "TUSHARE_PRO"} and not settings.market_data_provider_enabled:
        return False
    if normalized == "AKSHARE_EASTMONEY":
        return settings.market_data_akshare_enabled and not settings.is_production
    if normalized == "AKSHARE_SINA_DAILY":
        return settings.market_data_akshare_sina_enabled and not settings.is_production
    if normalized == "BAOSTOCK":
        return settings.market_data_baostock_enabled and not settings.is_production
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
    if normalized in {"AKSHARE_EASTMONEY", "AKSHARE_SINA_DAILY", "BAOSTOCK", "TUSHARE_PRO"}:
        return provider_class(settings)
    return provider_class()


def route_market_data_provider_for_exchange(exchange: str) -> str:
    normalized = exchange.strip().upper()
    if normalized in TRIAL_ROUTE_BY_EXCHANGE:
        return TRIAL_ROUTE_BY_EXCHANGE[normalized]
    raise ValueError(f"No market data trial route configured for exchange: {exchange}")


def route_market_data_provider_for_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if "." not in normalized:
        raise ValueError(f"Market data routing requires normalized symbol with exchange suffix: {symbol}")
    return route_market_data_provider_for_exchange(normalized.rsplit(".", 1)[1])


def market_data_provider_catalog(settings: Settings) -> list[dict[str, object]]:
    return [
        {
            "source_code": "AKSHARE_EASTMONEY",
            "display_name": "AKShare / Eastmoney A-share Daily",
            "implemented": True,
            "enabled_by_config": is_market_data_provider_enabled("AKSHARE_EASTMONEY", settings),
            "source_type": "third_party_data_service",
            "authorization_status": "unverified",
            "usage_scope": ["local_development", "internal_testing"],
            "production_enabled": False,
            "capabilities": ["daily_snapshot", "trade_calendar"],
            "limitations": [
                "AKShare wraps Eastmoney public web data; it is not exchange official, realtime, or production-authorized.",
                "Downgraded to diagnostic and explicit cross-check use; it is not the default persistence route.",
            ],
        },
        {
            "source_code": "AKSHARE_SINA_DAILY",
            "display_name": "AKShare / Sina BJ Daily",
            "implemented": True,
            "enabled_by_config": is_market_data_provider_enabled("AKSHARE_SINA_DAILY", settings),
            "source_type": "third_party_data_service",
            "authorization_status": "unverified",
            "usage_scope": ["local_development", "internal_testing"],
            "production_enabled": False,
            "capabilities": ["daily_snapshot", "trade_calendar"],
            "limitations": [
                "AKShare wraps Sina daily data for BJ low-frequency validation; it is not official, realtime, or production-authorized.",
                "Only explicit BJ route local development and internal testing are allowed.",
            ],
        },
        {
            "source_code": "BAOSTOCK",
            "display_name": "BaoStock A-share Daily",
            "implemented": True,
            "enabled_by_config": is_market_data_provider_enabled("BAOSTOCK", settings),
            "source_type": "third_party_data_service",
            "authorization_status": "unverified",
            "usage_scope": ["local_development", "internal_testing"],
            "production_enabled": False,
            "capabilities": ["daily_snapshot", "trade_calendar", "cross_check"],
            "limitations": [
                "BaoStock is the explicit SH/SZ five-day local trial route.",
                "It is not exchange official, realtime, or production-authorized; BJ is not handled by this adapter.",
            ],
        },
        {
            "source_code": "TUSHARE_PRO",
            "display_name": "Tushare Pro",
            "implemented": True,
            "enabled_by_config": is_market_data_provider_enabled("TUSHARE_PRO", settings),
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
