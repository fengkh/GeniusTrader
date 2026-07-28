from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_frontend_market_pages_do_not_use_mock_market_state():
    files = [
        ROOT / "src" / "app" / "today" / "page.tsx",
        ROOT / "src" / "app" / "watchlist" / "page.tsx",
        ROOT / "src" / "app" / "watchlist" / "[stockId]" / "page.tsx",
        ROOT / "src" / "app" / "settings" / "market-data" / "page.tsx",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "useMockState" not in text
        assert "StockChartPanel" not in text
        assert "SimulatedDataBadge" not in text
        assert "/mock/" not in text

    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "getMarketDataStatus" in combined
    assert "getWatchlistMarketSnapshots" in combined
    assert "getStockMarketSnapshot" in combined


def test_frontend_empty_market_copy_is_explicit():
    text = (ROOT / "src" / "app" / "watchlist" / "[stockId]" / "page.tsx").read_text(encoding="utf-8")
    assert "暂无真实行情数据" in text
    assert "页面不会补造模拟走势" in text
    assert "AI 生成行情数字" in text
