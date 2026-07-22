from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SPIKE_ROOT = Path(__file__).resolve().parents[1]
if str(SPIKE_ROOT) not in sys.path:
    sys.path.insert(0, str(SPIKE_ROOT))


def make_daily(
    symbol: str,
    *,
    start_close: float = 10.0,
    multiplier: float = 1.01,
    days: int = 70,
    amount: float = 50_000_000,
    turnover_rate: float = 2.0,
    suspended: bool = False,
) -> pd.DataFrame:
    rows = []
    close = start_close
    start = pd.Timestamp("2026-03-01")
    for index in range(days):
        pre_close = close
        close = close * multiplier
        rows.append(
            {
                "symbol": symbol,
                "trade_date": (start + pd.Timedelta(days=index)).date().isoformat(),
                "open": pre_close,
                "high": max(pre_close, close) * 1.01,
                "low": min(pre_close, close) * 0.99,
                "close": close,
                "pre_close": pre_close,
                "pct_change": (close / pre_close - 1) * 100,
                "volume": 10_000_000 + index * 10_000,
                "amount": amount + index * 100_000,
                "turnover_rate": turnover_rate + index * 0.01,
                "trade_status": "suspended" if suspended and index == days - 1 else "trading",
                "is_st": False,
            }
        )
    return pd.DataFrame(rows)
