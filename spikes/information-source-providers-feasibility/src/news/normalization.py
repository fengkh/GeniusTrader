from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import NewsRecord
from ..date_utils import parse_datetime
from ..normalization import normalize_symbol
from ..url_utils import normalize_url


def match_symbols(text: str, known_symbols: list[str]) -> list[str]:
    matched: list[str] = []
    for symbol in known_symbols:
        code = symbol.split(".")[0]
        if code in text and symbol not in matched:
            matched.append(symbol)
    return matched


def build_news_record(
    *,
    provider: str,
    provider_id: str | None,
    title: str,
    source_name: str,
    published_at: str | None,
    source_url: str,
    source_type: str,
    extracted_text: str | None,
    known_symbols: list[str],
    payload: dict[str, Any],
    fetched_at: datetime | None,
) -> NewsRecord:
    searchable = f"{title} {extracted_text or ''}"
    normalized_symbols = []
    for symbol in known_symbols:
        normalized_symbols.append(normalize_symbol(symbol))
    return NewsRecord(
        provider=provider,
        provider_item_id=provider_id,
        title=title,
        source_name=source_name,
        author=payload.get("author"),
        published_at=parse_datetime(published_at),
        updated_at=parse_datetime(payload.get("updated_at")),
        source_url=normalize_url(source_url),
        canonical_url=normalize_url(payload.get("canonical_url")) if payload.get("canonical_url") else None,
        summary=payload.get("summary"),
        extracted_text=extracted_text,
        source_type=source_type,
        related_symbols=match_symbols(searchable, normalized_symbols),
        fetched_at=fetched_at,
        extraction_status="extracted" if extracted_text else "content_unavailable",
        provider_payload_reference={k: payload.get(k) for k in sorted(payload)[:20]},
    )
