from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

FORMULA_VERSION = "gt-market-breadth-v0.1"


def as_frame(data: pd.DataFrame | list[dict[str, Any]] | None) -> pd.DataFrame:
    if data is None:
        return pd.DataFrame()
    if isinstance(data, pd.DataFrame):
        return data.copy()
    return pd.DataFrame(data)


def to_numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def market_limit_threshold(symbol: str | None, is_st: bool = False) -> float:
    if is_st:
        return 4.8
    symbol = symbol or ""
    code = symbol.split(".")[0]
    suffix = symbol.split(".")[-1].upper() if "." in symbol else ""
    if suffix == "BJ" or code.startswith(("8", "4", "92")):
        return 29.5
    if code.startswith(("300", "301", "688")):
        return 19.5
    return 9.5


def _is_suspended(row: pd.Series) -> bool:
    status = str(row.get("trade_status", "")).strip().lower()
    if status in {"suspended", "halted", "停牌", "0"}:
        return True
    if pd.isna(row.get("close")) and pd.isna(row.get("pct_change")):
        return True
    return False


def _pct_change(row: pd.Series) -> float | None:
    value = row.get("pct_change")
    if pd.notna(value):
        return float(value)
    close = row.get("close")
    pre_close = row.get("pre_close")
    if pd.notna(close) and pd.notna(pre_close) and pre_close:
        return float((close / pre_close - 1) * 100)
    return None


def _latest_trade_date(frame: pd.DataFrame, fallback: str | None) -> str | None:
    if "trade_date" in frame.columns and not frame["trade_date"].dropna().empty:
        return str(frame["trade_date"].dropna().max())
    return fallback


def _history_for_symbol(history_by_symbol: dict[str, pd.DataFrame] | None, symbol: str) -> pd.DataFrame:
    if not history_by_symbol:
        return pd.DataFrame()
    frame = history_by_symbol.get(symbol)
    if frame is None:
        frame = history_by_symbol.get(symbol.split(".")[0])
    return as_frame(frame)


def _new_high_low_and_ma20(
    symbol: str,
    row: pd.Series,
    history_by_symbol: dict[str, pd.DataFrame] | None,
) -> tuple[bool | None, bool | None, bool | None]:
    history = _history_for_symbol(history_by_symbol, symbol)
    if history.empty:
        return None, None, None
    history = to_numeric(history, ["close", "high", "low"])
    if "trade_date" in history.columns:
        history = history.sort_values("trade_date")
    else:
        history = history.sort_index()
    recent = history.dropna(subset=["close"]).tail(20)
    if len(recent) < 20:
        return None, None, None
    current_close = row.get("close")
    if pd.isna(current_close):
        current_close = recent["close"].iloc[-1]
    high_value = row.get("high")
    low_value = row.get("low")
    current_high = current_close if pd.isna(high_value) else high_value
    current_low = current_close if pd.isna(low_value) else low_value
    return (
        bool(current_high >= recent["high"].max()) if "high" in recent.columns else bool(current_close >= recent["close"].max()),
        bool(current_low <= recent["low"].min()) if "low" in recent.columns else bool(current_close <= recent["close"].min()),
        bool(current_close > recent["close"].mean()),
    )


def _segment_performance(active: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    if column not in active.columns or active.empty:
        return []
    rows = []
    for name, group in active.groupby(column, dropna=True):
        pct = pd.to_numeric(group["computed_pct_change"], errors="coerce").dropna()
        rows.append(
            {
                "segment": str(name),
                "count": int(len(group)),
                "average_pct_change": None if pct.empty else float(pct.mean()),
                "median_pct_change": None if pct.empty else float(pct.median()),
            }
        )
    return sorted(rows, key=lambda item: item["segment"])


def compute_market_breadth(
    snapshot: pd.DataFrame | list[dict[str, Any]] | None,
    *,
    history_by_symbol: dict[str, pd.DataFrame] | None = None,
    previous_total_amount: float | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    frame = as_frame(snapshot)
    if frame.empty:
        return {
            "status": "PASS_EMPTY",
            "formula_version": FORMULA_VERSION,
            "as_of_date": as_of_date,
            "missing_reasons": ["snapshot empty"],
            "stock_count": 0,
            "up_count": None,
            "down_count": None,
            "flat_count": None,
            "suspended_count": None,
            "limit_up_count": None,
            "limit_down_count": None,
            "total_amount": None,
            "amount_change_pct": None,
            "new_high_20d_count": None,
            "new_low_20d_count": None,
            "above_ma20_ratio": None,
            "median_pct_change": None,
        }

    frame = to_numeric(
        frame,
        ["open", "high", "low", "close", "pre_close", "pct_change", "amount", "total_market_value"],
    )
    frame["computed_pct_change"] = frame.apply(_pct_change, axis=1)
    frame["is_suspended"] = frame.apply(_is_suspended, axis=1)
    active = frame[~frame["is_suspended"]].copy()
    active_pct = pd.to_numeric(active["computed_pct_change"], errors="coerce")
    missing_reasons: list[str] = []
    if active_pct.isna().any():
        missing_reasons.append("some active rows miss pct_change or close/pre_close")

    up_count = int((active_pct > 0).sum())
    down_count = int((active_pct < 0).sum())
    flat_count = int((active_pct == 0).sum())
    suspended_count = int(frame["is_suspended"].sum())

    limit_up = 0
    limit_down = 0
    for _, row in active.iterrows():
        pct = row.get("computed_pct_change")
        if pd.isna(pct):
            continue
        threshold = market_limit_threshold(str(row.get("symbol", "")), bool(row.get("is_st", False)))
        if pct >= threshold:
            limit_up += 1
        if pct <= -threshold:
            limit_down += 1

    total_amount = None
    if "amount" in active.columns:
        amounts = pd.to_numeric(active["amount"], errors="coerce").dropna()
        if amounts.empty:
            missing_reasons.append("amount missing")
        else:
            total_amount = float(amounts.sum())
    amount_change_pct = None
    if total_amount is not None and previous_total_amount:
        amount_change_pct = float((total_amount / previous_total_amount - 1) * 100)

    new_high_values: list[bool] = []
    new_low_values: list[bool] = []
    above_ma20_values: list[bool] = []
    for _, row in active.iterrows():
        symbol = str(row.get("symbol", ""))
        new_high, new_low, above_ma20 = _new_high_low_and_ma20(symbol, row, history_by_symbol)
        if new_high is not None:
            new_high_values.append(new_high)
        if new_low is not None:
            new_low_values.append(new_low)
        if above_ma20 is not None:
            above_ma20_values.append(above_ma20)
    if history_by_symbol and not above_ma20_values:
        missing_reasons.append("history insufficient for MA20/new high/new low")
    if history_by_symbol is None:
        missing_reasons.append("history missing for MA20/new high/new low")

    by_market = _segment_performance(active, "market")
    large_small = []
    if "total_market_value" in active.columns:
        cap = pd.to_numeric(active["total_market_value"], errors="coerce")
        if cap.dropna().size >= 2:
            median_cap = float(cap.median())
            cap_group = active.copy()
            cap_group["size_style"] = np.where(cap_group["total_market_value"] >= median_cap, "large_cap", "small_cap")
            large_small = _segment_performance(cap_group, "size_style")
        else:
            missing_reasons.append("market cap insufficient for size style")
    else:
        missing_reasons.append("market cap missing for size style")

    growth_value = _segment_performance(active, "style") if "style" in active.columns else []
    if not growth_value:
        missing_reasons.append("style proxy missing")

    return {
        "status": "PASS" if active_pct.notna().any() else "DATA_INSUFFICIENT",
        "formula_version": FORMULA_VERSION,
        "as_of_date": _latest_trade_date(frame, as_of_date),
        "missing_reasons": missing_reasons,
        "stock_count": int(len(frame)),
        "active_count": int(len(active)),
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": flat_count,
        "suspended_count": suspended_count,
        "limit_up_count": limit_up,
        "limit_down_count": limit_down,
        "total_amount": total_amount,
        "amount_change_pct": amount_change_pct,
        "new_high_20d_count": None if not new_high_values else int(sum(new_high_values)),
        "new_low_20d_count": None if not new_low_values else int(sum(new_low_values)),
        "above_ma20_ratio": None if not above_ma20_values else float(sum(above_ma20_values) / len(above_ma20_values) * 100),
        "median_pct_change": None if active_pct.dropna().empty else float(active_pct.median()),
        "market_segment_performance": by_market,
        "large_small_performance": large_small,
        "growth_value_performance": growth_value,
        "input_scope": "full_snapshot" if len(frame) > 1000 else "limited_sample",
    }


def summarize_breadth_status(results: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(item.get("status", "UNKNOWN") for item in results))
