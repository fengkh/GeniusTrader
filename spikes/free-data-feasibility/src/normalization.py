from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

EMPTY_MARKERS = {"", "--", "-", "None", "none", "NaN", "nan", "NULL", "null", "N/A", "n/a"}

NORMALIZED_UNITS = {
    "volume": "share",
    "amount": "CNY_yuan",
    "turnover_rate": "percent_value",
    "pct_change": "percent_value",
    "amplitude": "percent_value",
    "market_value": "CNY_yuan",
}


def empty_to_none(value: Any) -> Any | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    if text in EMPTY_MARKERS:
        return None
    return value


def to_float(value: Any) -> float | None:
    value = empty_to_none(value)
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip().replace(",", "").replace("%", "")
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def to_int_like(value: Any) -> float | None:
    parsed = to_float(value)
    if parsed is None:
        return None
    return float(parsed)


def percent_value(value: Any) -> float | None:
    return to_float(value)


def volume_to_shares(value: Any, original_unit: str) -> float | None:
    parsed = to_float(value)
    if parsed is None:
        return None
    unit = original_unit.lower()
    if unit in {"hand", "lot", "手"}:
        return parsed * 100
    if unit in {"share", "shares", "股"}:
        return parsed
    if unit in {"10k_share", "万股"}:
        return parsed * 10000
    return parsed


def amount_to_yuan(value: Any, original_unit: str) -> float | None:
    parsed = to_float(value)
    if parsed is None:
        return None
    unit = original_unit.lower()
    if unit in {"yuan", "cny_yuan", "元"}:
        return parsed
    if unit in {"10k_yuan", "万元"}:
        return parsed * 10000
    if unit in {"100m_yuan", "亿元"}:
        return parsed * 100000000
    return parsed


def normalize_symbol(value: Any) -> str | None:
    value = empty_to_none(value)
    if value is None:
        return None
    text = str(value).strip()
    lowered = text.lower()
    if lowered.startswith(("sh.", "sz.", "bj.")):
        exchange, code = lowered.split(".", 1)
        return f"{code.upper()}.{exchange.upper()}"
    if "." in text:
        code, exchange = text.split(".", 1)
        if exchange.upper() in {"SH", "SZ", "BJ"}:
            return f"{code.zfill(6)}.{exchange.upper()}"
    code = "".join(ch for ch in text if ch.isdigit())
    if len(code) < 6:
        code = code.zfill(6)
    else:
        code = code[-6:]
    if code.startswith(("6", "5", "9")):
        return f"{code}.SH"
    if code.startswith(("0", "2", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return f"{code}.UNKNOWN"


def provider_symbol(symbol: str, provider: str) -> str:
    normalized = normalize_symbol(symbol) or symbol
    code, exchange = normalized.split(".", 1) if "." in normalized else (normalized, "")
    provider = provider.lower()
    if provider in {"akshare", "efinance"}:
        return code
    if provider == "baostock":
        prefix = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(exchange.upper(), exchange.lower())
        return f"{prefix}.{code}"
    return normalized


def provider_index_symbol(index_code: str, provider: str) -> str:
    normalized = normalize_symbol(index_code) or index_code
    code, exchange = normalized.split(".", 1) if "." in normalized else (normalized, "")
    if provider.lower() == "baostock":
        prefix = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(exchange.upper(), exchange.lower())
        return f"{prefix}.{code}"
    return code


def normalize_date(value: Any) -> str | None:
    value = empty_to_none(value)
    if value is None:
        return None
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    try:
        return pd.to_datetime(text).date().isoformat()
    except (TypeError, ValueError):
        return text


def normalize_datetime(value: Any) -> str | None:
    value = empty_to_none(value)
    if value is None:
        return None
    try:
        return pd.to_datetime(value).isoformat()
    except (TypeError, ValueError):
        return str(value)


def _get(frame: pd.DataFrame, row_index: int, column: str | None) -> Any:
    if column is None or column not in frame.columns:
        return None
    return frame.iloc[row_index][column]


def normalize_by_mapping(
    frame: pd.DataFrame,
    *,
    mapping: dict[str, str | None],
    provider: str,
    provider_symbol_value: str | None = None,
    defaults: dict[str, Any] | None = None,
    volume_unit: str = "share",
    amount_unit: str = "yuan",
) -> pd.DataFrame:
    defaults = defaults or {}
    rows: list[dict[str, Any]] = []
    for row_index in range(len(frame)):
        row: dict[str, Any] = dict(defaults)
        for internal_field, source_column in mapping.items():
            raw = _get(frame, row_index, source_column)
            if internal_field == "symbol":
                row[internal_field] = normalize_symbol(raw)
            elif internal_field in {"trade_date", "effective_date", "list_date", "delist_date"}:
                row[internal_field] = normalize_date(raw)
            elif internal_field in {"datetime", "quote_time", "fetched_at"}:
                row[internal_field] = normalize_datetime(raw)
            elif internal_field == "volume":
                row[internal_field] = volume_to_shares(raw, volume_unit)
            elif internal_field == "amount":
                row[internal_field] = amount_to_yuan(raw, amount_unit)
            elif internal_field in {
                "open",
                "high",
                "low",
                "close",
                "pre_close",
                "change",
                "pct_change",
                "turnover_rate",
                "volume_ratio",
                "total_market_value",
                "circulating_market_value",
                "amplitude",
            }:
                row[internal_field] = to_float(raw)
            else:
                row[internal_field] = empty_to_none(raw)
        if "provider_symbol" not in row:
            row["provider_symbol"] = provider_symbol_value or _get(frame, row_index, mapping.get("symbol"))
        row["provider"] = provider
        rows.append(row)
    return pd.DataFrame(rows)


def with_missing_columns(frame: pd.DataFrame, fields: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for field in fields:
        if field not in result.columns:
            result[field] = None
    return result[fields]


def select_bse_symbol_from_snapshot(snapshot: pd.DataFrame) -> tuple[str | None, str | None]:
    if snapshot.empty:
        return None, "snapshot is empty"
    symbol_column = "symbol" if "symbol" in snapshot.columns else "代码" if "代码" in snapshot.columns else None
    if symbol_column is None:
        return None, "symbol field missing"
    normalized = snapshot[symbol_column].map(normalize_symbol).dropna()
    candidates = sorted(symbol for symbol in normalized if symbol.endswith(".BJ"))
    if not candidates:
        return None, "no BSE symbol found"
    return candidates[0], None


def amount_volume_reasonableness(frame: pd.DataFrame) -> tuple[bool, str]:
    required = {"open", "high", "low", "close", "volume", "amount"}
    if not required.issubset(frame.columns):
        return False, "required OHLC/volume/amount fields missing"
    valid = frame.dropna(subset=["open", "high", "low", "close", "volume", "amount"])
    if valid.empty:
        return False, "no rows with complete amount and volume"
    latest = valid.iloc[-1]
    avg_price = (float(latest["open"]) + float(latest["high"]) + float(latest["low"]) + float(latest["close"])) / 4
    expected = avg_price * float(latest["volume"])
    amount = float(latest["amount"])
    if expected <= 0 or amount <= 0:
        return False, "latest amount or estimated turnover is non-positive"
    ratio = amount / expected
    return 0.1 <= ratio <= 10, f"latest amount/(avg_price*volume) ratio={ratio:.4f}"
