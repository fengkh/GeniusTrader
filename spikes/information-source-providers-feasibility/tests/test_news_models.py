from datetime import datetime
from zoneinfo import ZoneInfo

from src.news.normalization import build_news_record


def test_news_record_completeness_and_symbol_matching():
    record = build_news_record(
        provider="public_news",
        provider_id="1",
        title="600519 公司新闻",
        source_name="Example",
        published_at="2026-07-24",
        source_url="https://example.com/news",
        source_type="public_web",
        extracted_text="正文提到 600519",
        known_symbols=["600519.SH"],
        payload={},
        fetched_at=datetime(2026, 7, 24, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    data = record.to_dict()
    assert data["data_completeness"] == "complete"
    assert data["related_symbols"] == ["600519.SH"]


def test_news_summary_not_treated_as_full_text():
    record = build_news_record(
        provider="rss",
        provider_id="1",
        title="标题",
        source_name="RSS",
        published_at=None,
        source_url="https://example.com/rss/1",
        source_type="rss",
        extracted_text=None,
        known_symbols=[],
        payload={"summary": "摘要"},
        fetched_at=None,
    )
    assert "extracted_text" in record.missing_fields
