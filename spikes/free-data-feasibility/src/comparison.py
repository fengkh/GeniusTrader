from __future__ import annotations

from itertools import combinations
from typing import Any

import pandas as pd

from .models import ComparisonFieldResult

DEFAULT_TOLERANCES = {
    "open": (0.001, 0.0002),
    "high": (0.001, 0.0002),
    "low": (0.001, 0.0002),
    "close": (0.001, 0.0002),
    "volume": (100.0, 0.001),
    "amount": (100.0, 0.001),
    "turnover_rate": (0.01, 0.001),
    "pct_change": (0.01, 0.001),
}


def common_trade_dates(frames: dict[str, pd.DataFrame]) -> list[str]:
    date_sets: list[set[str]] = []
    for frame in frames.values():
        if frame.empty:
            continue
        if "trade_date" in frame.columns:
            date_sets.append(set(frame["trade_date"].dropna().astype(str)))
        elif frame.index.name == "trade_date":
            date_sets.append(set(frame.index.dropna().astype(str)))
    if not date_sets:
        return []
    return sorted(set.intersection(*date_sets))


def compare_daily_frames(
    *,
    symbol: str,
    provider_frames: dict[str, pd.DataFrame],
    fields: list[str] | None = None,
) -> list[ComparisonFieldResult]:
    fields = fields or list(DEFAULT_TOLERANCES)
    results: list[ComparisonFieldResult] = []
    usable = {
        provider: _frame_by_date(frame)
        for provider, frame in provider_frames.items()
        if not frame.empty and "trade_date" in frame.columns
    }
    for provider_a, provider_b in combinations(sorted(usable), 2):
        dates = common_trade_dates({provider_a: usable[provider_a], provider_b: usable[provider_b]})
        left = usable[provider_a].loc[dates] if dates else pd.DataFrame()
        right = usable[provider_b].loc[dates] if dates else pd.DataFrame()
        for field in fields:
            results.append(_compare_field(symbol, provider_a, provider_b, field, left, right))
    return results


def compare_adjusted_return_frames(
    *,
    symbol: str,
    provider_frames: dict[str, pd.DataFrame],
    windows: list[int] | None = None,
) -> list[ComparisonFieldResult]:
    windows = windows or [5, 10, 20]
    return_frames: dict[str, pd.DataFrame] = {}
    for provider, frame in provider_frames.items():
        if frame.empty or "trade_date" not in frame.columns or "close" not in frame.columns:
            continue
        sorted_frame = frame.sort_values("trade_date").copy()
        for window in windows:
            sorted_frame[f"qfq_return_{window}d"] = pd.to_numeric(sorted_frame["close"], errors="coerce").pct_change(window) * 100
        return_frames[provider] = sorted_frame
    return compare_daily_frames(
        symbol=symbol,
        provider_frames=return_frames,
        fields=[f"qfq_return_{window}d" for window in windows],
    )


def _frame_by_date(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["trade_date"] = result["trade_date"].astype(str)
    return result.drop_duplicates("trade_date").set_index("trade_date").sort_index()


def _compare_field(
    symbol: str,
    provider_a: str,
    provider_b: str,
    field: str,
    left: pd.DataFrame,
    right: pd.DataFrame,
) -> ComparisonFieldResult:
    if left.empty or right.empty:
        return _empty_result(symbol, provider_a, provider_b, field, "no common trade dates")
    if field not in left.columns or field not in right.columns:
        return _empty_result(symbol, provider_a, provider_b, field, "field missing in one or both providers")
    abs_tolerance, rel_tolerance = DEFAULT_TOLERANCES.get(field, (0.01, 0.001))
    pairs = pd.DataFrame(
        {
            "date": left.index,
            "left": pd.to_numeric(left[field], errors="coerce"),
            "right": pd.to_numeric(right[field], errors="coerce"),
        }
    ).dropna(subset=["left", "right"])
    if pairs.empty:
        return _empty_result(symbol, provider_a, provider_b, field, "no comparable numeric rows")
    abs_diff = (pairs["left"] - pairs["right"]).abs()
    denominator = pairs["right"].abs().where(pairs["right"].abs() > 0, 1.0)
    rel_diff = abs_diff / denominator
    exact = abs_diff == 0
    within = (abs_diff <= abs_tolerance) | (rel_diff <= rel_tolerance)
    mismatches = pairs[~within].head(5)
    return ComparisonFieldResult(
        symbol=symbol,
        provider_a=provider_a,
        provider_b=provider_b,
        field=field,
        compared_rows=int(len(pairs)),
        exact_match_rows=int(exact.sum()),
        within_tolerance_rows=int(within.sum()),
        mismatch_rows=int((~within).sum()),
        max_absolute_difference=float(abs_diff.max()) if not abs_diff.empty else None,
        max_relative_difference=float(rel_diff.max()) if not rel_diff.empty else None,
        mismatch_examples=_mismatch_examples(mismatches, field),
        likely_reason=_likely_reason(field, int((~within).sum())),
    )


def _empty_result(symbol: str, provider_a: str, provider_b: str, field: str, reason: str) -> ComparisonFieldResult:
    return ComparisonFieldResult(
        symbol=symbol,
        provider_a=provider_a,
        provider_b=provider_b,
        field=field,
        compared_rows=0,
        exact_match_rows=0,
        within_tolerance_rows=0,
        mismatch_rows=0,
        max_absolute_difference=None,
        max_relative_difference=None,
        mismatch_examples=[],
        likely_reason=reason,
    )


def _mismatch_examples(frame: pd.DataFrame, field: str) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        examples.append(
            {
                "trade_date": str(row["date"]),
                "field": field,
                "provider_a_value": None if pd.isna(row["left"]) else float(row["left"]),
                "provider_b_value": None if pd.isna(row["right"]) else float(row["right"]),
            }
        )
    return examples


def _likely_reason(field: str, mismatch_rows: int) -> str:
    if mismatch_rows == 0:
        return "within tolerance"
    if field in {"volume", "amount"}:
        return "possible unit convention, suspended-row handling, rounding or upstream revision difference"
    if field == "turnover_rate":
        return "possible free-float denominator or rounding difference"
    if field.startswith("qfq_return_"):
        return "possible adjusted-price base date or corporate-action algorithm difference"
    return "possible rounding, revision or upstream source difference"
