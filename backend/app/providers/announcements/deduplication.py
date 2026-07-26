import hashlib
import json
from typing import Any


def stable_json_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def announcement_deduplication_key(
    *,
    source_code: str,
    provider_announcement_id: str | None,
    normalized_title: str,
    published_at_iso: str | None,
    stock_symbols: list[str],
    document_url: str | None,
) -> str:
    return stable_json_hash(
        {
            "source_code": source_code,
            "provider_announcement_id": provider_announcement_id,
            "normalized_title": normalized_title,
            "published_at": published_at_iso,
            "stock_symbols": sorted(stock_symbols),
            "document_url": document_url,
        }
    )

