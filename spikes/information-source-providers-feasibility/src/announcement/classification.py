from __future__ import annotations

from dataclasses import dataclass

from ..normalization import normalize_title


@dataclass(slots=True)
class AnnouncementClassification:
    category: str
    rule: str


RULES = [
    ("periodic_report", ["年度报告", "半年度报告", "季度报告", "年报", "季报"]),
    ("earnings_forecast", ["业绩预告", "业绩预增", "业绩预减", "业绩预亏"]),
    ("earnings_flash", ["业绩快报"]),
    ("shareholder_change", ["增持", "减持", "权益变动"]),
    ("buyback", ["回购"]),
    ("equity_incentive", ["股权激励", "限制性股票"]),
    ("major_contract", ["重大合同", "合同公告"]),
    ("external_investment", ["对外投资", "投资设立"]),
    ("restructuring", ["重大资产重组", "并购", "收购"]),
    ("refinancing", ["非公开发行", "定向增发", "可转债", "再融资"]),
    ("litigation", ["诉讼", "仲裁"]),
    ("administrative_penalty", ["行政处罚", "监管措施"]),
    ("risk_warning", ["风险提示", "退市风险"]),
    ("trading_halt", ["停牌", "复牌"]),
    ("meeting", ["董事会", "股东大会", "监事会"]),
    ("executive_change", ["高管", "董事辞职", "聘任"]),
    ("dividend", ["分红", "派息", "权益分派"]),
    ("correction", ["更正", "补充公告", "修订"]),
]


def classify_announcement(title: str) -> AnnouncementClassification:
    normalized = normalize_title(title)
    for category, keywords in RULES:
        for keyword in keywords:
            if keyword.lower() in normalized:
                return AnnouncementClassification(category=category, rule=f"title_contains:{keyword}")
    return AnnouncementClassification(category="other", rule="no_title_rule_matched")
