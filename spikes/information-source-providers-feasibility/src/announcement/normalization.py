from __future__ import annotations

from datetime import datetime
from typing import Any

from .classification import classify_announcement
from .models import AnnouncementRecord
from ..date_utils import parse_datetime
from ..normalization import normalize_symbol
from ..url_utils import normalize_url


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


def build_announcement_record(
    *,
    provider: str,
    provider_id: str | None,
    title: str,
    published_at: str | int | float | None,
    source_page_url: str,
    document_url: str | None,
    company_name: str | None,
    symbols: list[str] | str | None,
    exchange: str | None,
    payload: dict[str, Any],
    fetched_at: datetime | None,
) -> AnnouncementRecord:
    classification = classify_announcement(title)
    return AnnouncementRecord(
        provider=provider,
        provider_announcement_id=provider_id,
        announcement_id_stability="provider_id" if provider_id else "derived",
        title=title,
        announcement_type=classification.category,
        published_at=parse_datetime(published_at),
        company_name=company_name,
        stock_symbols=normalize_symbols(symbols),
        exchange=exchange,
        source_page_url=normalize_url(source_page_url),
        document_url=normalize_url(document_url) if document_url else None,
        is_pdf=bool(document_url and document_url.lower().split("?")[0].endswith(".pdf")),
        fetched_at=fetched_at,
        provider_payload_reference={k: payload.get(k) for k in sorted(payload)[:20]},
    )
