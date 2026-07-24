from datetime import datetime
from zoneinfo import ZoneInfo

from src.announcement.models import AnnouncementRecord


def test_announcement_record_completeness_and_keys():
    record = AnnouncementRecord(
        provider="cninfo",
        provider_announcement_id="abc",
        announcement_id_stability="provider_id",
        title="年度报告",
        announcement_type="periodic_report",
        published_at=datetime(2026, 7, 24, tzinfo=ZoneInfo("Asia/Shanghai")),
        company_name="贵州茅台",
        stock_symbols=["600519.SH"],
        exchange="SH",
        source_page_url="https://example.com/detail",
        document_url="https://example.com/a.pdf",
    )
    data = record.to_dict()
    assert data["data_completeness"] == "complete"
    assert data["deduplication_key"]
    assert data["effective_date"] == "2026-07-24"


def test_announcement_record_missing_fields_are_explicit():
    record = AnnouncementRecord(
        provider="bse",
        provider_announcement_id=None,
        announcement_id_stability="derived",
        title="",
        announcement_type="other",
        published_at=None,
        company_name=None,
        stock_symbols=[],
        exchange="BJ",
        source_page_url="https://example.com",
    )
    assert "title" in record.missing_fields
    assert record.data_completeness in {"partial", "insufficient"}
