import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def normalize_symbol(value: str) -> str:
    raw = value.strip().upper()
    if "." in raw:
        code, exchange = raw.split(".", 1)
        if exchange in {"SH", "SSE"}:
            return f"{code}.SH"
        if exchange in {"SZ", "SZSE"}:
            return f"{code}.SZ"
        if exchange in {"BJ", "BSE"}:
            return f"{code}.BJ"
        return raw
    if raw.startswith(("5", "6", "9")):
        return f"{raw}.SH" if not raw.startswith("9") else f"{raw}.BJ"
    if raw.startswith(("0", "1", "2", "3")):
        return f"{raw}.SZ"
    return raw


def normalize_tushare_symbol(value: str) -> str:
    raw = value.strip().upper()
    if raw.endswith(".SSE"):
        return f"{raw[:-4]}.SH"
    if raw.endswith(".SZSE"):
        return f"{raw[:-5]}.SZ"
    if raw.endswith(".BSE"):
        return f"{raw[:-4]}.BJ"
    return normalize_symbol(raw)


def to_tushare_symbol(value: str) -> str:
    symbol = normalize_symbol(value)
    code, exchange = symbol.split(".", 1)
    suffix = {"SH": "SH", "SZ": "SZ", "BJ": "BJ"}.get(exchange, exchange)
    return f"{code}.{suffix}"


def decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def decimal_times(value: Any, multiplier: str) -> Decimal | None:
    parsed = decimal_or_none(value)
    return parsed * Decimal(multiplier) if parsed is not None else None


def ratio_or_percent_to_percent_number(value: Any) -> Decimal | None:
    parsed = decimal_or_none(value)
    if parsed is None:
        return None
    if parsed != 0 and abs(parsed) < Decimal("0.1"):
        return parsed * Decimal("100")
    return parsed


def parse_trade_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def completeness_for_required(values: dict[str, Any], required: list[str]) -> str:
    missing = [field for field in required if values.get(field) is None]
    if not missing:
        return "complete"
    if len(missing) <= 2:
        return "usable"
    if values.get("close") is not None and values.get("trade_date") is not None:
        return "partial"
    return "insufficient"


def stable_hash(payload: dict[str, Any]) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
