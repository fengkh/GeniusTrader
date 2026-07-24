from src.announcement.classification import classify_announcement
from src.announcement.normalization import normalize_symbols
from src.normalization import normalize_symbol, normalize_title


def test_symbol_normalization_infers_exchange():
    assert normalize_symbol("600519") == "600519.SH"
    assert normalize_symbol("000001") == "000001.SZ"
    assert normalize_symbol("430047") == "430047.BJ"


def test_symbol_list_skips_invalid_values():
    assert normalize_symbols(["600519", "bad", "300750.SZ"]) == ["600519.SH", "300750.SZ"]


def test_title_normalization_and_classification():
    assert "年度报告" in normalize_title("【贵州茅台】2025 年度报告")
    result = classify_announcement("关于回购公司股份方案的公告")
    assert result.category == "buyback"
    assert result.rule.startswith("title_contains")
