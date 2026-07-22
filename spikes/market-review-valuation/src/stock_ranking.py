from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .board_metrics import consecutive_rising_days, latest_pct_change, percentile_rank, return_rate, sort_daily
from .market_breadth import market_limit_threshold

FORMULA_VERSION = "gt-board-stock-ranking-v0.1"


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    frame = frame.copy()
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _percentile(frame: pd.DataFrame, column: str, window: int = 60) -> tuple[float | None, str | None]:
    if column not in frame.columns:
        return None, f"{column} missing"
    series = pd.to_numeric(frame[column], errors="coerce").dropna().tail(window)
    if len(series) < min(window, 5):
        return None, f"need at least {min(window, 5)} valid rows"
    return percentile_rank(series)


def _is_suspended(latest: pd.Series) -> bool:
    status = str(latest.get("trade_status", "")).lower()
    return status in {"suspended", "halted", "停牌", "0"}


def _risk_penalties(symbol: str, latest: pd.Series, amount: float | None) -> list[dict[str, Any]]:
    penalties = []
    if _is_suspended(latest):
        penalties.append({"type": "suspended", "points": 35, "reason": "stock is suspended or not trading"})
    if bool(latest.get("is_st", False)) or str(latest.get("name", "")).upper().startswith("ST"):
        penalties.append({"type": "st", "points": 20, "reason": "ST or abnormal status"})
    if amount is None or amount < 20_000_000:
        penalties.append({"type": "low_liquidity", "points": 10, "reason": "latest amount below sample liquidity floor or missing"})
    if symbol.endswith(".BJ"):
        penalties.append({"type": "bse_sample", "points": 5, "reason": "BSE liquidity and limit rules require separate validation"})
    return penalties


def _new_high_20d(frame: pd.DataFrame) -> bool | None:
    frame = _numeric(sort_daily(frame), ["close", "high"])
    valid = frame.dropna(subset=["close"]).tail(20)
    if len(valid) < 20:
        return None
    high_col = "high" if "high" in valid.columns and valid["high"].notna().any() else "close"
    return bool(valid["close"].iloc[-1] >= valid[high_col].max())


def compute_stock_metrics(
    symbol: str,
    frame: pd.DataFrame,
    *,
    board_return_5d: float | None,
    index_return_5d: float | None,
    event_count: int = 0,
) -> dict[str, Any]:
    daily = _numeric(sort_daily(frame), ["close", "pre_close", "pct_change", "volume", "amount", "turnover_rate"])
    if daily.empty:
        return {
            "symbol": symbol,
            "status": "DATA_INSUFFICIENT",
            "score": None,
            "missing_reasons": ["daily empty"],
            "formula_version": FORMULA_VERSION,
        }
    latest = daily.iloc[-1]
    pct_1d, pct_reason = latest_pct_change(daily)
    pct_3d, reason_3d = return_rate(daily, 3)
    pct_5d, reason_5d = return_rate(daily, 5)
    volume_percentile, volume_reason = _percentile(daily, "volume")
    amount_percentile, amount_reason = _percentile(daily, "amount")
    turnover_percentile, turnover_reason = _percentile(daily, "turnover_rate")
    amount = None if pd.isna(latest.get("amount")) else float(latest["amount"])
    limit_threshold = market_limit_threshold(symbol, bool(latest.get("is_st", False)))
    touched_limit = bool(pct_1d is not None and pct_1d >= limit_threshold)
    new_high_20d = _new_high_20d(daily)
    relative_board = pct_5d - board_return_5d if pct_5d is not None and board_return_5d is not None else None
    relative_index = pct_5d - index_return_5d if pct_5d is not None and index_return_5d is not None else None
    penalties = _risk_penalties(symbol, latest, amount)
    missing = [
        reason
        for reason in [pct_reason, reason_3d, reason_5d, volume_reason, amount_reason, turnover_reason]
        if reason
    ]
    data_points = [
        pct_1d,
        pct_3d,
        pct_5d,
        volume_percentile,
        amount_percentile,
        turnover_percentile,
        relative_board,
        relative_index,
    ]
    data_completeness = sum(item is not None for item in data_points) / len(data_points) * 100
    raw_score_parts = [
        _clip_score(pct_1d, 0, 2),
        _clip_score(pct_3d, 0, 4),
        _clip_score(pct_5d, 0, 6),
        volume_percentile,
        amount_percentile,
        turnover_percentile,
        _clip_score(relative_board, 0, 3),
        _clip_score(relative_index, 0, 3),
        100 if touched_limit else 40,
        80 if new_high_20d else 30 if new_high_20d is False else None,
        min(event_count * 20, 100),
    ]
    available_scores = [float(item) for item in raw_score_parts if item is not None]
    penalty_points = sum(item["points"] for item in penalties)
    score = None if not available_scores else max(0.0, min(100.0, float(np.mean(available_scores)) - penalty_points))
    return {
        "symbol": symbol,
        "as_of_date": str(latest.get("trade_date", "")) or None,
        "status": "PASS" if score is not None else "DATA_INSUFFICIENT",
        "score": None if score is None else round(score, 4),
        "metrics": {
            "return_1d": pct_1d,
            "return_3d": pct_3d,
            "return_5d": pct_5d,
            "consecutive_rising_days": consecutive_rising_days(daily),
            "relative_board_strength": relative_board,
            "relative_index_strength": relative_index,
            "volume_percentile": volume_percentile,
            "amount_percentile": amount_percentile,
            "turnover_rate_percentile": turnover_percentile,
            "is_limit_up_or_touched": touched_limit,
            "is_20d_new_high": new_high_20d,
            "event_count": event_count,
            "latest_amount": amount,
        },
        "risk_penalties": penalties,
        "data_completeness": round(data_completeness, 4),
        "missing_reasons": missing,
        "formula_version": FORMULA_VERSION,
    }


def _clip_score(value: float | None, center: float, scale: float) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(np.clip(50 + (value - center) / max(scale, 0.0001) * 10, 0, 100))


def _role_suggestion(row: dict[str, Any], rank: int) -> dict[str, Any]:
    metrics = row.get("metrics", {})
    score = row.get("score") or 0
    if rank == 1 and score >= 65 and (metrics.get("relative_board_strength") or 0) > 0:
        role = "leader_candidate"
        confidence = "medium"
    elif (metrics.get("amount_percentile") or 0) >= 70 and score >= 55:
        role = "core_liquidity_candidate"
        confidence = "low"
    elif score >= 50:
        role = "follow_candidate"
        confidence = "low"
    else:
        role = "observe_only"
        confidence = "low"
    return {
        "role": role,
        "confidence": confidence,
        "is_system_suggestion": True,
        "user_can_correct": True,
        "rule": "based on rank, relative board strength, amount percentile and risk penalties",
    }


def rank_stocks_within_board(
    *,
    board_id: str,
    board_name: str,
    stock_frames: dict[str, pd.DataFrame],
    board_return_5d: float | None = None,
    index_return_5d: float | None = None,
    events_by_symbol: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for symbol, frame in stock_frames.items():
        row = compute_stock_metrics(
            symbol,
            frame,
            board_return_5d=board_return_5d,
            index_return_5d=index_return_5d,
            event_count=(events_by_symbol or {}).get(symbol, 0),
        )
        row["board_id"] = board_id
        row["board_name"] = board_name
        rows.append(row)
    rows.sort(
        key=lambda item: (
            item["score"] is None,
            -(item["score"] if item["score"] is not None else -1),
            -item["data_completeness"],
            item["symbol"],
        ),
    )
    for index, row in enumerate(rows, start=1):
        row["rank_in_board"] = index
        row["role_suggestion"] = _role_suggestion(row, index)
    return rows
