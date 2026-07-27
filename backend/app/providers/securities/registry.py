from app.core.config import Settings
from app.providers.securities.baostock import BaoStockSecurityMasterProvider
from app.providers.securities.base import SecurityMasterProvider
from app.providers.securities.bse import BseSecurityMasterProvider
from app.providers.securities.sse import SseSecurityMasterProvider
from app.providers.securities.szse import SzseSecurityMasterProvider

SECURITY_MASTER_SOURCE_CODES = [
    "SSE_SECURITY_MASTER",
    "SZSE_SECURITY_MASTER",
    "BSE_SECURITY_MASTER",
    "BAOSTOCK_DEVELOPMENT_FALLBACK",
]


BAOSTOCK_SOURCE_ALIASES = {
    "BAOSTOCK_SECURITY_MASTER": "BAOSTOCK_DEVELOPMENT_FALLBACK",
}


def normalize_security_master_source_code(source_code: str) -> str:
    normalized = source_code.strip().upper()
    return BAOSTOCK_SOURCE_ALIASES.get(normalized, normalized)


def get_security_master_provider(source_code: str, settings: Settings) -> SecurityMasterProvider | None:
    normalized = normalize_security_master_source_code(source_code)
    if normalized == "SSE_SECURITY_MASTER":
        return SseSecurityMasterProvider(settings)
    if normalized == "SZSE_SECURITY_MASTER":
        return SzseSecurityMasterProvider(settings)
    if normalized == "BSE_SECURITY_MASTER":
        return BseSecurityMasterProvider(settings)
    if normalized == "BAOSTOCK_DEVELOPMENT_FALLBACK":
        return BaoStockSecurityMasterProvider(settings)
    return None


def is_security_master_provider_enabled(source_code: str, settings: Settings) -> bool:
    normalized = normalize_security_master_source_code(source_code)
    if normalized == "SSE_SECURITY_MASTER":
        return settings.security_master_sse_enabled
    if normalized == "SZSE_SECURITY_MASTER":
        return settings.security_master_szse_enabled
    if normalized == "BSE_SECURITY_MASTER":
        return settings.security_master_bse_enabled
    if normalized == "BAOSTOCK_DEVELOPMENT_FALLBACK":
        return settings.security_master_baostock_enabled
    return False


def security_master_provider_catalog(settings: Settings) -> list[dict]:
    return [
        _catalog_item(
            source_code="SSE_SECURITY_MASTER",
            display_name="上海证券交易所证券目录",
            official=True,
            enabled_by_config=settings.security_master_sse_enabled,
            limitations=["官方公开来源候选；稳定性和授权仍需验证。"],
        ),
        _catalog_item(
            source_code="SZSE_SECURITY_MASTER",
            display_name="深圳证券交易所体系证券目录",
            official=True,
            enabled_by_config=settings.security_master_szse_enabled,
            limitations=["若无稳定官方接口，必须记录 DATA_INSUFFICIENT。"],
        ),
        _catalog_item(
            source_code="BSE_SECURITY_MASTER",
            display_name="北京证券交易所证券目录",
            official=True,
            enabled_by_config=settings.security_master_bse_enabled,
            limitations=["公开页面/接口候选；字段完整性待验证。"],
        ),
        _catalog_item(
            source_code="BAOSTOCK_DEVELOPMENT_FALLBACK",
            display_name="BaoStock 开发补充证券目录",
            official=False,
            enabled_by_config=settings.security_master_baostock_enabled,
            limitations=["非官方来源，仅作开发补充或交叉核验。"],
        ),
    ]


def _catalog_item(
    *,
    source_code: str,
    display_name: str,
    official: bool,
    enabled_by_config: bool,
    limitations: list[str],
) -> dict:
    return {
        "source_code": source_code,
        "display_name": display_name,
        "implemented": True,
        "enabled_by_config": enabled_by_config,
        "official": official,
        "capabilities": ["security_master"],
        "limitations": limitations,
    }
