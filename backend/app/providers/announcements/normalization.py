import re
import unicodedata
from datetime import UTC, datetime, timezone
from zoneinfo import ZoneInfo

from app.core.url_security import normalize_url
from app.providers.announcements.classification import classify_announcement
from app.providers.announcements.deduplication import (
    announcement_deduplication_key,
    stable_json_hash,
)
from app.providers.announcements.models import NormalizedAnnouncement, RawAnnouncementRecord

CN_TZ = ZoneInfo("Asia/Shanghai")
SYMBOL_RE = re.compile(r"^(?P<code>\d{6})(?:\.(?P<exchange>SH|SZ|BJ))?$", re.I)
REQUIRED_FIELDS = ["provider_announcement_id", "title", "published_at", "source_page_url"]


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value)
    return " ".join(text.replace("\u3000", " ").split())


def normalize_title_text(value: str | None) -> str:
    text = normalize_text(value)
    text = re.sub(r"[【】\[\]（）()]", " ", text)
    return " ".join(text.split()).lower()


def parse_provider_datetime(value: str | int | float | None, *, default_tz: timezone = CN_TZ) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, int | float):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp, UTC).astimezone(default_tz)
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=default_tz)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=default_tz)


def normalize_symbol(value: str) -> str:
    text = value.strip().upper()
    match = SYMBOL_RE.match(text)
    if not match:
        raise ValueError(f"invalid A-share symbol: {value}")
    code = match.group("code")
    exchange = match.group("exchange")
    if not exchange:
        if code.startswith(("6", "9")):
            exchange = "SH"
        elif code.startswith(("0", "2", "3")):
            exchange = "SZ"
        elif code.startswith(("4", "8")):
            exchange = "BJ"
        else:
            raise ValueError(f"cannot infer exchange for symbol: {value}")
    return f"{code}.{exchange}"


def symbol_without_exchange(value: str) -> str:
    return normalize_symbol(value).split(".")[0]


def normalize_symbols(values: list[str] | str | None) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [item.strip() for item in values.replace(";", ",").split(",") if item.strip()]
    normalized: list[str] = []
    for value in values:
        try:
            symbol = normalize_symbol(value)
        except ValueError:
            continue
        if symbol not in normalized:
            normalized.append(symbol)
    return normalized


def build_normalized_announcement(
    *,
    source_code: str,
    raw: RawAnnouncementRecord,
    fetched_at: datetime,
) -> NormalizedAnnouncement:
    title = normalize_text(raw.title)
    normalized_title = normalize_title_text(title)
    classification = classify_announcement(title)
    published_at = parse_provider_datetime(raw.published_at)
    source_page_url = normalize_url(raw.source_page_url).normalized_url
    document_url = normalize_url(raw.document_url).normalized_url if raw.document_url else None
    stock_symbols = normalize_symbols(raw.stock_symbols)
    missing_fields = _missing_fields(raw, stock_symbols, document_url)
    data_completeness = _data_completeness(missing_fields, title, source_page_url)
    raw_metadata_hash = stable_json_hash(_safe_payload_reference(raw.raw_payload))
    deduplication_key = announcement_deduplication_key(
        source_code=source_code,
        provider_announcement_id=raw.provider_record_id,
        normalized_title=normalized_title,
        published_at_iso=published_at.isoformat() if published_at else None,
        stock_symbols=stock_symbols,
        document_url=document_url,
    )
    return NormalizedAnnouncement(
        source_code=source_code,
        provider_announcement_id=raw.provider_record_id,
        title=title,
        normalized_title=normalized_title,
        announcement_type=classification.category,
        announcement_type_confidence=classification.confidence,
        announcement_type_basis=classification.basis,
        published_at=published_at,
        company_name=normalize_text(raw.company_name) or None,
        stock_symbols=stock_symbols,
        exchange=raw.exchange,
        source_page_url=source_page_url,
        document_url=document_url,
        attachment_urls=[document_url] if document_url else [],
        is_pdf=bool(document_url and document_url.lower().split("?", 1)[0].endswith(".pdf")),
        is_correction=classification.category == "correction",
        corrected_announcement_id=None,
        raw_metadata_hash=raw_metadata_hash,
        deduplication_key=deduplication_key,
        data_completeness=data_completeness,
        missing_fields=missing_fields,
        fetched_at=fetched_at,
    )


def _safe_payload_reference(payload: dict[str, object]) -> dict[str, object]:
    allowed: dict[str, object] = {}
    for key in sorted(payload)[:24]:
        value = payload[key]
        if isinstance(value, str) and len(value) > 500:
            allowed[key] = f"{value[:500]}..."
        else:
            allowed[key] = value
    return allowed


def _missing_fields(raw: RawAnnouncementRecord, symbols: list[str], document_url: str | None) -> list[str]:
    missing: list[str] = []
    for field_name in REQUIRED_FIELDS:
        value = getattr(raw, field_name)
        if value is None or value == "":
            missing.append(field_name)
    if not symbols:
        missing.append("stock_symbols")
    if not document_url:
        missing.append("document_url")
    return missing


def _data_completeness(missing: list[str], title: str, source_page_url: str) -> str:
    missing_set = set(missing)
    if not missing_set:
        return "complete"
    if not title or not source_page_url:
        return "insufficient"
    if not ({"provider_announcement_id", "published_at"} & missing_set):
        return "usable"
    return "partial"
