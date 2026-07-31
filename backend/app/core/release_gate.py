from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from cryptography.fernet import Fernet
from sqlalchemy.engine import make_url

from app.core.config import Settings

ReleaseStatus = Literal["pass", "warning", "fail"]

PLACEHOLDER_MARKERS = (
    "change-me",
    "placeholder",
    "example",
    "base64-fernet-key",
    "fernet_key",
)

WEAK_BOOTSTRAP_PASSWORDS = {
    "admin",
    "password",
    "password123",
    "1234567890",
    "changeme123",
    "geniustrader123",
}


@dataclass(frozen=True)
class ReleaseCheckItem:
    code: str
    status: ReleaseStatus
    message: str
    details: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "status": self.status,
            "message": self.message,
            "details": self.details,
        }


def production_settings_checks(settings: Settings) -> list[ReleaseCheckItem]:
    items: list[ReleaseCheckItem] = []
    if not settings.is_production:
        items.append(
            ReleaseCheckItem(
                "APP_ENV_NOT_PRODUCTION",
                "warning",
                "APP_ENV 不是 production；发布检查以非生产配置运行。",
                {"app_env": settings.app_env},
            )
        )
        return items

    items.extend(_production_blockers(settings))
    if any(origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost") for origin in settings.cors_origins):
        items.append(
            ReleaseCheckItem(
                "CORS_LOCAL_ORIGIN_IN_PRODUCTION",
                "warning",
                "生产 CORS allowlist 包含本地开发来源。",
            )
        )
    if settings.announcement_real_network_enabled and not (
        settings.announcement_cninfo_enabled or settings.announcement_sse_enabled
    ):
        items.append(
            ReleaseCheckItem(
                "ANNOUNCEMENT_NETWORK_WITHOUT_PROVIDER",
                "warning",
                "公告真实网络已开启，但 CNINFO/SSE 均未启用。",
            )
        )
    if not (settings.announcement_cninfo_enabled or settings.announcement_sse_enabled):
        items.append(
            ReleaseCheckItem(
                "OFFICIAL_ANNOUNCEMENT_PROVIDERS_DISABLED",
                "warning",
                "CNINFO 与 SSE_DISCLOSURE 均未启用；官方公告上线前需由管理员或部署配置显式开启。",
            )
        )
    return items


def validate_production_startup_settings(settings: Settings) -> None:
    if not settings.is_production:
        return
    blockers = _production_blockers(settings)
    if blockers:
        codes = ", ".join(item.code for item in blockers)
        raise RuntimeError(f"Production configuration rejected: {codes}")


def private_beta_feature_matrix(settings: Settings) -> list[dict[str, object]]:
    return [
        {"feature": "SECURITY_MASTER_READ", "enabled": True, "reason": "本地 stocks 主数据只读检索。"},
        {"feature": "WATCHLIST", "enabled": True, "reason": "真实用户自选股闭环已接入。"},
        {
            "feature": "OFFICIAL_ANNOUNCEMENTS",
            "enabled": settings.announcement_cninfo_enabled or settings.announcement_sse_enabled,
            "reason": "仅允许 CNINFO/SSE_DISCLOSURE 由部署配置显式启用。",
        },
        {"feature": "USER_AI_BYOK", "enabled": True, "reason": "用户自带 API Key，经后端 AI Gateway 调用。"},
        {"feature": "DAILY_REVIEWS", "enabled": True, "reason": "用户主动生成每日复盘。"},
        {"feature": "MARKET_DATA", "enabled": False, "reason": "暂无经授权的真实行情数据。"},
        {"feature": "PUBLIC_REGISTRATION", "enabled": settings.public_registration_enabled, "reason": "私人测试版必须关闭。"},
        {"feature": "AUTO_TRADING", "enabled": False, "reason": "产品不是交易系统。"},
        {"feature": "SOCIAL_CRAWLING", "enabled": False, "reason": "第一版不做全网社交平台爬虫。"},
    ]


def backup_status_item(backup_dir: str | None = None) -> ReleaseCheckItem:
    path = Path(backup_dir or os.environ.get("BACKUP_DIR", "backups"))
    if not path.exists():
        return ReleaseCheckItem(
            "RECENT_BACKUP_NOT_FOUND",
            "warning",
            "未发现备份目录；上线前需在服务器完成 pg_dump/restore 演练。",
            {"backup_dir": str(path)},
        )
    backups = sorted(path.glob("*.dump"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not backups:
        return ReleaseCheckItem(
            "RECENT_BACKUP_NOT_FOUND",
            "warning",
            "备份目录中未发现 .dump 文件；上线前需在服务器完成备份恢复演练。",
            {"backup_dir": str(path)},
        )
    latest = backups[0]
    return ReleaseCheckItem(
        "RECENT_BACKUP_FOUND",
        "pass",
        "发现最近备份文件。",
        {"backup_dir": str(path), "latest_backup": latest.name, "size_bytes": latest.stat().st_size},
    )


def tmp_dir_status_item(tmp_dir: str | None = None) -> ReleaseCheckItem:
    path = Path(tmp_dir or os.environ.get("TMPDIR") or os.environ.get("TEMP") or "tmp")
    exists = path.exists()
    writable = os.access(path if exists else path.parent, os.W_OK)
    return ReleaseCheckItem(
        "TMP_DIR_WRITABLE" if writable else "TMP_DIR_NOT_WRITABLE",
        "pass" if writable else "fail",
        "临时目录可写。" if writable else "临时目录不可写或父目录不可写。",
        {"tmp_dir": str(path), "exists": exists},
    )


def _production_blockers(settings: Settings) -> list[ReleaseCheckItem]:
    blockers: list[ReleaseCheckItem] = []
    if settings.debug:
        blockers.append(ReleaseCheckItem("DEBUG_TRUE", "fail", "生产环境禁止 DEBUG=true。"))
    blockers.extend(_encryption_key_blockers(settings))
    if not settings.session_cookie_secure:
        blockers.append(
            ReleaseCheckItem("SESSION_COOKIE_INSECURE", "fail", "生产环境必须启用 Secure Cookie。")
        )
    if not settings.cors_origins or "*" in settings.cors_origins:
        blockers.append(ReleaseCheckItem("CORS_WILDCARD", "fail", "生产 CORS 必须是明确 allowlist，禁止通配。"))
    if not settings.trusted_host_list or "*" in settings.trusted_host_list:
        blockers.append(
            ReleaseCheckItem("TRUSTED_HOSTS_WILDCARD", "fail", "生产 Trusted Hosts 必须是明确域名，禁止通配。")
        )
    blockers.extend(_database_url_blockers(settings))
    if settings.public_registration_enabled:
        blockers.append(
            ReleaseCheckItem("PUBLIC_REGISTRATION_ENABLED", "fail", "私人测试版生产环境禁止公众注册。")
        )
    if _weak_bootstrap_password(settings.admin_bootstrap_password):
        blockers.append(
            ReleaseCheckItem("DEFAULT_ADMIN_PASSWORD", "fail", "生产环境禁止使用弱默认管理员初始密码。")
        )
    if settings.security_master_baostock_enabled:
        blockers.append(
            ReleaseCheckItem(
                "BAOSTOCK_ENABLED_IN_PRODUCTION",
                "fail",
                "BaoStock 仅为 development fallback，生产环境禁止启用。",
            )
        )
    if settings.announcement_bse_enabled:
        blockers.append(
            ReleaseCheckItem(
                "BSE_DISCLOSURE_ENABLED_IN_PRODUCTION",
                "fail",
                "BSE_DISCLOSURE 仍为候选来源，真实 Smoke 前生产默认关闭。",
            )
        )
    if settings.market_data_mock_enabled:
        blockers.append(
            ReleaseCheckItem("MARKET_DATA_MOCK_ENABLED", "fail", "生产环境禁止启用 Mock 行情 Provider。")
        )
    if settings.market_data_akshare_enabled:
        blockers.append(
            ReleaseCheckItem(
                "AKSHARE_EASTMONEY_ENABLED_IN_PRODUCTION",
                "fail",
                "AKShare / Eastmoney is unverified and must stay disabled in production.",
            )
        )
    if settings.market_data_akshare_sina_enabled:
        blockers.append(
            ReleaseCheckItem(
                "AKSHARE_SINA_DAILY_ENABLED_IN_PRODUCTION",
                "fail",
                "AKShare / Sina daily is unverified and must stay disabled in production.",
            )
        )
    if settings.market_data_baostock_enabled:
        blockers.append(
            ReleaseCheckItem(
                "BAOSTOCK_MARKET_DATA_ENABLED_IN_PRODUCTION",
                "fail",
                "BaoStock market data is unverified and must stay disabled in production.",
            )
        )
    if _market_enabled(settings) and settings.market_data_tushare_authorization_status != "commercially_authorized":
        blockers.append(
            ReleaseCheckItem(
                "UNAUTHORIZED_MARKET_PROVIDER_ENABLED",
                "fail",
                "行情 Provider 未确认商业授权时，生产环境禁止启用真实行情网络或同步。",
            )
        )
    return blockers


def _market_enabled(settings: Settings) -> bool:
    return any(
        [
            settings.market_data_provider_enabled,
            settings.market_data_sync_enabled,
            settings.market_data_real_network_enabled,
            settings.market_data_tushare_enabled,
            settings.market_data_akshare_enabled,
            settings.market_data_akshare_sina_enabled,
            settings.market_data_baostock_enabled,
        ]
    )


def _encryption_key_blockers(settings: Settings) -> list[ReleaseCheckItem]:
    if not settings.encryption_keys:
        return [ReleaseCheckItem("APP_ENCRYPTION_KEYS_MISSING", "fail", "生产环境必须配置 APP_ENCRYPTION_KEYS。")]
    blockers: list[ReleaseCheckItem] = []
    for key in settings.encryption_keys:
        lowered = key.lower()
        if any(marker in lowered for marker in PLACEHOLDER_MARKERS):
            blockers.append(
                ReleaseCheckItem(
                    "APP_ENCRYPTION_KEYS_PLACEHOLDER",
                    "fail",
                    "APP_ENCRYPTION_KEYS 仍是示例或占位值。",
                )
            )
            continue
        try:
            Fernet(key.encode("ascii"))
        except (ValueError, TypeError):
            blockers.append(
                ReleaseCheckItem(
                    "APP_ENCRYPTION_KEYS_INVALID",
                    "fail",
                    "APP_ENCRYPTION_KEYS 不是有效 Fernet Key。",
                )
            )
    return blockers


def _database_url_blockers(settings: Settings) -> list[ReleaseCheckItem]:
    blockers: list[ReleaseCheckItem] = []
    try:
        url = make_url(settings.database_url)
    except Exception:
        return [ReleaseCheckItem("DATABASE_URL_INVALID", "fail", "DATABASE_URL 无法解析。")]
    host = (url.host or "").lower()
    if host in {"127.0.0.1", "localhost", "::1"}:
        blockers.append(
            ReleaseCheckItem(
                "DATABASE_URL_LOCALHOST",
                "fail",
                "生产 DATABASE_URL 不应指向 localhost；容器部署应使用内部服务名。",
            )
        )
    password = url.password or ""
    lowered_password = password.lower()
    if not password or any(marker in lowered_password for marker in PLACEHOLDER_MARKERS) or lowered_password in {"postgres", "password"}:
        blockers.append(
            ReleaseCheckItem("DATABASE_PASSWORD_EXAMPLE", "fail", "生产数据库密码缺失或仍为示例值。")
        )
    return blockers


def _weak_bootstrap_password(value: str) -> bool:
    password = value.strip()
    if not password:
        return False
    return password.lower() in WEAK_BOOTSTRAP_PASSWORDS or any(marker in password.lower() for marker in PLACEHOLDER_MARKERS)
