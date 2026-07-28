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
    files = [
        ROOT / "src" / "app" / "today" / "page.tsx",
        ROOT / "src" / "app" / "watchlist" / "page.tsx",
        ROOT / "src" / "app" / "watchlist" / "[stockId]" / "page.tsx",
        ROOT / "src" / "app" / "settings" / "market-data" / "page.tsx",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "暂无经授权的真实行情数据" in combined
    assert "AI 生成行情数字" in combined
    assert "Mock K线" not in combined
    assert "0元" not in combined
    assert "0%" not in combined


def test_frontend_release_operations_page_documents_private_beta_matrix():
    text = (ROOT / "src" / "app" / "settings" / "operations" / "page.tsx").read_text(encoding="utf-8")

    assert "SECURITY_MASTER_READ" in text
    assert "OFFICIAL_ANNOUNCEMENTS" in text
    assert "MARKET_DATA" in text
    assert "暂无经授权的真实行情数据" in text


def test_market_review_mock_route_is_closed_for_release():
    reviews_text = (ROOT / "src" / "app" / "reviews" / "page.tsx").read_text(encoding="utf-8")
    market_review_text = (ROOT / "src" / "app" / "market-review" / "[date]" / "page.tsx").read_text(
        encoding="utf-8"
    )

    assert "/market-review/" not in reviews_text
    assert "useMockState" not in market_review_text
    assert "MarketReviewDetail" not in market_review_text
    assert "SimulatedDataBadge" not in market_review_text
    assert "不展示 Mock 指数" in market_review_text
    assert "暂无经授权的真实全市场行情数据" in market_review_text
