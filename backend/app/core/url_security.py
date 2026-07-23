import hashlib
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode


@dataclass(frozen=True)
class ValidatedUrl:
    original_url: str
    normalized_url: str
    host: str


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_blocked_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return any(
        (
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        )
    )


def resolve_host_addresses(host: str) -> list[str]:
    try:
        records = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise AppError(ErrorCode.URL_INVALID, "URL 主机无法解析", status_code=422) from exc
    return sorted({record[4][0] for record in records})


def _validate_no_private_addresses(host: str) -> None:
    try:
        if _is_blocked_ip(host):
            raise AppError(ErrorCode.URL_PRIVATE_ADDRESS_BLOCKED, "URL 指向内网或保留地址", status_code=422)
        return
    except ValueError:
        pass
    for address in resolve_host_addresses(host):
        if _is_blocked_ip(address):
            raise AppError(ErrorCode.URL_PRIVATE_ADDRESS_BLOCKED, "URL 指向内网或保留地址", status_code=422)


def normalize_url(raw_url: str) -> ValidatedUrl:
    parsed = urlsplit(raw_url.strip())
    if not parsed.scheme or not parsed.netloc or not parsed.hostname:
        raise AppError(ErrorCode.URL_INVALID, "URL 格式无效", status_code=422)
    if parsed.username or parsed.password:
        raise AppError(ErrorCode.URL_INVALID, "URL 不允许包含用户名或密码", status_code=422)
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower()
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or "/"
    tracking_keys = {"fbclid", "gclid", "yclid", "mc_cid", "mc_eid"}
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in tracking_keys
    ]
    query = urlencode(query_items, doseq=True)
    normalized = urlunsplit((scheme, f"{host}{port}", path, query, ""))
    return ValidatedUrl(
        original_url=raw_url.strip(),
        normalized_url=normalized if not query else normalized,
        host=host,
    )


def validate_public_content_url(raw_url: str) -> ValidatedUrl:
    validated = normalize_url(raw_url)
    scheme = urlsplit(validated.normalized_url).scheme
    if scheme not in {"http", "https"}:
        raise AppError(ErrorCode.URL_PROTOCOL_NOT_ALLOWED, "只允许抓取 http 或 https URL", status_code=422)
    _validate_no_private_addresses(validated.host)
    return validated


def validate_redirect_url(raw_url: str) -> ValidatedUrl:
    try:
        return validate_public_content_url(raw_url)
    except AppError as exc:
        raise AppError(ErrorCode.URL_REDIRECT_BLOCKED, "重定向目标被安全策略拦截", status_code=422) from exc


def validate_ai_base_url(raw_url: str, settings: Settings) -> ValidatedUrl:
    validated = normalize_url(raw_url)
    scheme = urlsplit(validated.normalized_url).scheme
    if scheme != "https" and not (settings.app_env == "development" and settings.allow_private_ai_base_url):
        raise AppError(ErrorCode.URL_PROTOCOL_NOT_ALLOWED, "AI Base URL 默认必须使用 https", status_code=422)
    if not settings.allow_private_ai_base_url:
        _validate_no_private_addresses(validated.host)
    return validated
