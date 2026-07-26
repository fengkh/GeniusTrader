import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnnouncementClassification:
    category: str
    confidence: float
    basis: dict[str, object]


RULES: list[tuple[str, float, list[str]]] = [
    ("correction", 0.9, ["\u66f4\u6b63", "\u8865\u5145\u516c\u544a", "\u4fee\u8ba2"]),
    ("periodic_report", 0.9, ["年度报告", "半年度报告", "季度报告", "年报", "季报"]),
    ("earnings_forecast", 0.88, ["业绩预告", "业绩预增", "业绩预减", "业绩预亏"]),
    ("earnings_flash", 0.88, ["业绩快报"]),
    ("shareholder_change", 0.84, ["增持", "减持", "权益变动"]),
    ("buyback", 0.86, ["回购"]),
    ("equity_incentive", 0.84, ["股权激励", "限制性股票"]),
    ("major_contract", 0.82, ["重大合同", "合同公告"]),
    ("external_investment", 0.8, ["对外投资", "投资设立"]),
    ("restructuring", 0.86, ["重大资产重组", "并购", "收购"]),
    ("refinancing", 0.82, ["非公开发行", "定向增发", "可转债", "再融资"]),
    ("litigation", 0.82, ["诉讼", "仲裁"]),
    ("administrative_penalty", 0.86, ["行政处罚", "监管措施"]),
    ("risk_warning", 0.84, ["风险提示", "退市风险"]),
    ("trading_halt", 0.86, ["停牌", "复牌"]),
    ("meeting", 0.72, ["董事会", "股东大会", "监事会"]),
    ("executive_change", 0.8, ["高管", "董事辞职", "聘任"]),
    ("dividend", 0.82, ["分红", "派息", "权益分派"]),
    ("correction", 0.9, ["更正", "补充公告", "修订"]),
]


def classify_announcement(title: str) -> AnnouncementClassification:
    normalized = _normalize_title_text(title)
    for category, confidence, keywords in RULES:
        for keyword in keywords:
            if keyword.lower() in normalized:
                return AnnouncementClassification(
                    category=category,
                    confidence=confidence,
                    basis={
                        "method": "deterministic_title_rule",
                        "matched_rule": f"title_contains:{keyword}",
                        "not_investment_judgment": True,
                    },
                )
    return AnnouncementClassification(
        category="other",
        confidence=0.2,
        basis={
            "method": "deterministic_title_rule",
            "matched_rule": "no_title_rule_matched",
            "not_investment_judgment": True,
        },
    )


def _normalize_title_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value)
    text = re.sub(r"[【】\[\]（）()]", " ", text.replace("\u3000", " "))
    return " ".join(text.split()).lower()
