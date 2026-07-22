from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

FORMULA_VERSION = "gt-board-heat-v0.1"


def as_frame(data: pd.DataFrame | list[dict[str, Any]] | None) -> pd.DataFrame:
    if data is None:
        return pd.DataFrame()
    if isinstance(data, pd.DataFrame):
        return data.copy()
    return pd.DataFrame(data)


def numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def sort_daily(frame: pd.DataFrame) -> pd.DataFrame:
    frame = as_frame(frame)
    if frame.empty:
        return frame
    if "trade_date" in frame.columns:
        return frame.sort_values("trade_date").reset_index(drop=True)
    return frame.reset_index(drop=True)


def return_rate(frame: pd.DataFrame, window: int, close_col: str = "close") -> tuple[float | None, str | None]:
    frame = numeric(sort_daily(frame), [close_col])
    if close_col not in frame.columns:
        return None, f"{close_col} missing"
    valid = frame.dropna(subset=[close_col])
    if len(valid) < window + 1:
        return None, f"need {window + 1} rows, got {len(valid)}"
    previous = valid[close_col].iloc[-window - 1]
    current = valid[close_col].iloc[-1]
    if pd.isna(previous) or previous == 0:
        return None, "previous value invalid"
    return float((current / previous - 1) * 100), None


def latest_pct_change(frame: pd.DataFrame) -> tuple[float | None, str | None]:
    frame = numeric(sort_daily(frame), ["pct_change", "close", "pre_close"])
    if frame.empty:
        return None, "empty daily"
    latest = frame.iloc[-1]
    if "pct_change" in frame.columns and pd.notna(latest.get("pct_change")):
        return float(latest["pct_change"]), None
    if pd.notna(latest.get("close")) and pd.notna(latest.get("pre_close")) and latest["pre_close"]:
        return float((latest["close"] / latest["pre_close"] - 1) * 100), None
    return None, "pct_change and close/pre_close missing"


def consecutive_rising_days(frame: pd.DataFrame) -> int:
    frame = numeric(sort_daily(frame), ["pct_change", "close"])
    if frame.empty:
        return 0
    count = 0
    for index in range(len(frame) - 1, -1, -1):
        row = frame.iloc[index]
        pct = row.get("pct_change")
        if pd.notna(pct):
            rising = float(pct) > 0
        elif index > 0 and pd.notna(row.get("close")) and pd.notna(frame.iloc[index - 1].get("close")):
            rising = float(row["close"]) > float(frame.iloc[index - 1]["close"])
        else:
            rising = False
        if not rising:
            break
        count += 1
    return count


def percentile_rank(values: pd.Series | list[float], current_value: float | None = None) -> tuple[float | None, str | None]:
    valid = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    if valid.empty:
        return None, "series has no valid values"
    current = float(valid.iloc[-1] if current_value is None else current_value)
    lower = (valid < current).sum()
    equal = (valid == current).sum()
    return float((lower + equal * 0.5) / len(valid) * 100), None


def _standardize(value: float | None, *, center: float = 0.0, scale: float = 1.0, minimum: float = 0.0, maximum: float = 100.0) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(np.clip(50 + (value - center) / scale * 10, minimum, maximum))


def component(
    name: str,
    raw_value: float | int | None,
    standardized_value: float | None,
    *,
    source: str,
    calc_date: str | None,
    missing_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "raw_value": None if raw_value is None or pd.isna(raw_value) else float(raw_value),
        "standardized_value": None if standardized_value is None or pd.isna(standardized_value) else float(standardized_value),
        "source": source,
        "calc_date": calc_date,
        "formula_version": FORMULA_VERSION,
        "missing_status": "PASS" if missing_reason is None else "DATA_INSUFFICIENT",
        "missing_reason": missing_reason,
    }


def _member_window_average(member_frames: dict[str, pd.DataFrame], window: int) -> tuple[float | None, str | None]:
    values = []
    reasons = []
    for frame in member_frames.values():
        value, reason = return_rate(frame, window)
        if value is None:
            reasons.append(reason or "missing")
        else:
            values.append(value)
    if not values:
        return None, "; ".join(sorted(set(reasons))) or "no member return"
    return float(np.mean(values)), None


def _latest_amount_series(member_frames: dict[str, pd.DataFrame]) -> pd.Series:
    rows = []
    for frame in member_frames.values():
        daily = numeric(sort_daily(frame), ["amount"])
        if not daily.empty and "amount" in daily.columns:
            rows.append(daily["amount"].tail(1))
    if not rows:
        return pd.Series(dtype=float)
    return pd.concat(rows).reset_index(drop=True)


def _board_amount_history(member_frames: dict[str, pd.DataFrame]) -> pd.Series:
    totals: dict[str, float] = {}
    for frame in member_frames.values():
        daily = numeric(sort_daily(frame), ["amount"])
        if daily.empty or "trade_date" not in daily.columns or "amount" not in daily.columns:
            continue
        for _, row in daily.dropna(subset=["amount"]).iterrows():
            totals[str(row["trade_date"])] = totals.get(str(row["trade_date"]), 0.0) + float(row["amount"])
    return pd.Series([totals[key] for key in sorted(totals)])


def _new_high_ratio(member_frames: dict[str, pd.DataFrame]) -> tuple[float | None, str | None]:
    flags = []
    for frame in member_frames.values():
        daily = numeric(sort_daily(frame), ["close", "high"])
        if len(daily.dropna(subset=["close"])) < 20:
            continue
        recent = daily.dropna(subset=["close"]).tail(20)
        current = float(recent["close"].iloc[-1])
        high_col = "high" if "high" in recent.columns and recent["high"].notna().any() else "close"
        flags.append(current >= float(recent[high_col].max()))
    if not flags:
        return None, "need member 20d histories"
    return float(sum(flags) / len(flags) * 100), None


def classify_board_status(metrics: dict[str, Any]) -> str:
    components = metrics.get("components", metrics)

    def raw(name: str) -> float | None:
        value = components.get(name, {}).get("raw_value") if isinstance(components.get(name), dict) else components.get(name)
        return None if value is None or pd.isna(value) else float(value)

    r1 = raw("return_1d")
    r3 = raw("return_3d")
    r5 = raw("return_5d")
    rising = raw("rising_ratio")
    leader = raw("leader_strength")
    consecutive = raw("consecutive_rising_days")
    if r1 is None or rising is None:
        return "data_insufficient"
    if r1 < -1.5 and rising < 40:
        return "retreat"
    if r5 is not None and r5 > 5 and rising < 45 and (leader or 0) > 4:
        return "high_divergence"
    if r1 > 2 and (r3 or 0) > 4 and rising > 65:
        return "accelerating"
    if (r5 or 0) > 5 and (consecutive or 0) >= 3 and rising > 55:
        return "sustained_strong"
    if r1 > 1.5 and (r3 is None or r3 <= 2) and rising > 55:
        return "new_start"
    if r1 > 0 and (r5 or 0) < 0:
        return "repair"
    return "data_insufficient" if (r3 is None and r5 is None) else "repair"


def compute_board_metrics(
    *,
    board_id: str,
    board_name: str,
    board_type: str,
    member_frames: dict[str, pd.DataFrame],
    index_frame: pd.DataFrame | None = None,
    as_of_date: str | None = None,
    provider: str = "local",
    previous_rank: int | None = None,
) -> dict[str, Any]:
    member_frames = {symbol: as_frame(frame) for symbol, frame in member_frames.items() if not as_frame(frame).empty}
    latest_returns: list[float] = []
    limit_up_count = 0
    turnover_rates: list[float] = []
    calc_date = as_of_date
    for symbol, frame in member_frames.items():
        daily = numeric(sort_daily(frame), ["pct_change", "turnover_rate", "close"])
        if daily.empty:
            continue
        if "trade_date" in daily.columns and calc_date is None:
            calc_date = str(daily["trade_date"].iloc[-1])
        pct, _ = latest_pct_change(daily)
        if pct is not None:
            latest_returns.append(pct)
            threshold = 19.5 if symbol.startswith(("300", "688")) else 9.5
            if pct >= threshold:
                limit_up_count += 1
        if "turnover_rate" in daily.columns and pd.notna(daily["turnover_rate"].iloc[-1]):
            turnover_rates.append(float(daily["turnover_rate"].iloc[-1]))

    return_1d = float(np.mean(latest_returns)) if latest_returns else None
    return_3d, r3_reason = _member_window_average(member_frames, 3)
    return_5d, r5_reason = _member_window_average(member_frames, 5)
    return_10d, r10_reason = _member_window_average(member_frames, 10)
    rising_ratio = None if not latest_returns else float(sum(1 for item in latest_returns if item > 0) / len(latest_returns) * 100)
    new_high_ratio, new_high_reason = _new_high_ratio(member_frames)
    latest_amounts = _latest_amount_series(member_frames)
    amount = None if latest_amounts.empty else float(latest_amounts.sum())
    amount_history = _board_amount_history(member_frames)
    amount_percentile, amount_percentile_reason = percentile_rank(amount_history) if not amount_history.empty else (None, "amount history missing")
    liquidity = None if not turnover_rates else float(np.mean(turnover_rates))
    leader_strength = None if not latest_returns else float(max(latest_returns))
    index_5d, index_reason = return_rate(as_frame(index_frame), 5) if index_frame is not None else (None, "index missing")
    relative_index_strength = return_5d - index_5d if return_5d is not None and index_5d is not None else None
    consecutive_days = max((consecutive_rising_days(frame) for frame in member_frames.values()), default=0)
    continuity = None if previous_rank is None else max(0.0, 100 - abs(previous_rank - 1) * 10)

    components = {
        "return_1d": component("return_1d", return_1d, _standardize(return_1d, scale=1), source=provider, calc_date=calc_date, missing_reason=None if return_1d is not None else "member latest return missing"),
        "return_3d": component("return_3d", return_3d, _standardize(return_3d, scale=2), source=provider, calc_date=calc_date, missing_reason=r3_reason),
        "return_5d": component("return_5d", return_5d, _standardize(return_5d, scale=3), source=provider, calc_date=calc_date, missing_reason=r5_reason),
        "return_10d": component("return_10d", return_10d, _standardize(return_10d, scale=5), source=provider, calc_date=calc_date, missing_reason=r10_reason),
        "relative_index_strength": component("relative_index_strength", relative_index_strength, _standardize(relative_index_strength, scale=2), source=provider, calc_date=calc_date, missing_reason=None if relative_index_strength is not None else index_reason),
        "rising_ratio": component("rising_ratio", rising_ratio, rising_ratio, source=provider, calc_date=calc_date, missing_reason=None if rising_ratio is not None else "latest returns missing"),
        "limit_up_count": component("limit_up_count", limit_up_count, min(limit_up_count * 20, 100), source=provider, calc_date=calc_date),
        "new_high_20d_ratio": component("new_high_20d_ratio", new_high_ratio, new_high_ratio, source=provider, calc_date=calc_date, missing_reason=new_high_reason),
        "amount": component("amount", amount, _standardize(amount, center=float(amount_history.median()) if not amount_history.empty else 0, scale=max(float(amount_history.std() or 1), 1)) if amount is not None else None, source=provider, calc_date=calc_date, missing_reason=None if amount is not None else "amount missing"),
        "amount_percentile": component("amount_percentile", amount_percentile, amount_percentile, source=provider, calc_date=calc_date, missing_reason=amount_percentile_reason),
        "liquidity": component("liquidity", liquidity, _standardize(liquidity, scale=2), source=provider, calc_date=calc_date, missing_reason=None if liquidity is not None else "turnover_rate missing"),
        "leader_strength": component("leader_strength", leader_strength, _standardize(leader_strength, scale=2), source=provider, calc_date=calc_date, missing_reason=None if leader_strength is not None else "leader missing"),
        "ranking_continuity": component("ranking_continuity", continuity, continuity, source=provider, calc_date=calc_date, missing_reason=None if continuity is not None else "previous rank missing"),
        "consecutive_rising_days": component("consecutive_rising_days", consecutive_days, min(consecutive_days * 20, 100), source=provider, calc_date=calc_date),
    }
    payload = {
        "board_id": board_id,
        "board_name": board_name,
        "board_type": board_type,
        "as_of_date": calc_date,
        "formula_version": FORMULA_VERSION,
        "member_count": len(member_frames),
        "components": components,
        "status": "PASS" if return_1d is not None and rising_ratio is not None else "DATA_INSUFFICIENT",
    }
    payload["board_stage"] = classify_board_status(payload)
    return payload

