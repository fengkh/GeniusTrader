from app.core.config import Settings
from app.providers.announcements.base import AnnouncementProvider
from app.providers.announcements.bse import BseAnnouncementProvider
from app.providers.announcements.cninfo import CninfoAnnouncementProvider
from app.providers.announcements.sse import SseAnnouncementProvider

IMPLEMENTED_ANNOUNCEMENT_PROVIDERS: dict[str, type[AnnouncementProvider]] = {
    "CNINFO": CninfoAnnouncementProvider,
    "SSE_DISCLOSURE": SseAnnouncementProvider,
    "BSE_DISCLOSURE": BseAnnouncementProvider,
}


def is_provider_enabled(source_code: str, settings: Settings) -> bool:
    if source_code == "CNINFO":
        return settings.announcement_cninfo_enabled
    if source_code == "SSE_DISCLOSURE":
        return settings.announcement_sse_enabled
    if source_code == "BSE_DISCLOSURE":
        return settings.announcement_bse_enabled
    return False


def get_announcement_provider(source_code: str, settings: Settings) -> AnnouncementProvider | None:
    provider_class = IMPLEMENTED_ANNOUNCEMENT_PROVIDERS.get(source_code)
    if not provider_class:
        return None
    return provider_class(settings)


def provider_catalog(settings: Settings) -> list[dict[str, object]]:
    run_limits = {
        "max_symbols_per_run": settings.announcement_max_symbols_per_run,
        "max_records_per_run": settings.announcement_max_records_per_run,
        "sync_lookback_days": settings.announcement_sync_lookback_days,
    }
    return [
        {
            "source_code": "CNINFO",
            "provider_adapter": "cninfo",
            "implemented": True,
            "enabled_by_config": settings.announcement_cninfo_enabled,
            "experimental": True,
            "capabilities": ["announcement_list", "announcement_pdf"],
            "limitations": ["实验性技术候选；授权、稳定性和完整性尚未最终确认。"],
            "limits": run_limits,
        },
        {
            "source_code": "SSE_DISCLOSURE",
            "provider_adapter": "sse",
            "implemented": True,
            "enabled_by_config": settings.announcement_sse_enabled,
            "experimental": True,
            "experimental_limited": True,
            "capabilities": ["announcement_list", "announcement_pdf"],
            "limitations": ["有限备选；小样本能力有限，不作为 CNINFO 自动回退。"],
            "limits": run_limits,
        },
        {
            "source_code": "SZSE_DISCLOSURE",
            "provider_adapter": "szse",
            "implemented": False,
            "enabled_by_config": False,
            "experimental": False,
            "capabilities": [],
            "limitations": ["本阶段证据不足，未实现真实网络 Adapter。"],
            "limits": run_limits,
        },
        {
            "source_code": "BSE_DISCLOSURE",
            "provider_adapter": "bse",
            "implemented": True,
            "enabled_by_config": settings.announcement_bse_enabled,
            "experimental": True,
            "experimental_limited": True,
            "capabilities": ["announcement_list", "announcement_pdf"],
            "limitations": ["北交所官方公告候选；真实网络可达性、字段稳定性和使用授权仍待补验。"],
            "limits": run_limits,
        },
    ]
