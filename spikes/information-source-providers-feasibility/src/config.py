from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path


DEFAULT_SYMBOLS = [
    "600519.SH",
    "000001.SZ",
    "300750.SZ",
    "688981.SH",
    "601318.SH",
    "000333.SZ",
    "002415.SZ",
    "603259.SH",
    "430047.BJ",
    "832000.BJ",
]


@dataclass(slots=True)
class SpikeConfig:
    providers: list[str]
    capabilities: list[str]
    date_from: date
    date_to: date
    symbols: list[str]
    max_records: int
    max_requests: int
    request_delay: float
    output_dir: Path
    skip_pdf: bool
    skip_news: bool
    skip_announcements: bool


def default_date_window(days: int = 30) -> tuple[date, date]:
    today = datetime.now(UTC).date()
    return today - timedelta(days=days), today


def parse_symbols(raw: str | None) -> list[str]:
    if not raw:
        return DEFAULT_SYMBOLS.copy()
    return [item.strip().upper() for item in raw.split(",") if item.strip()]
