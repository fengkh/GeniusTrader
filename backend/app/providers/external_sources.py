SOURCE_CATEGORIES = [
    "exchange_announcement",
    "company_disclosure",
    "government_policy",
    "government_notice",
    "regulator_release",
    "regulator_enforcement",
    "central_bank_release",
    "statistics_release",
    "international_official",
    "multilateral_organization",
    "licensed_financial_media",
    "public_financial_media",
    "company_news",
    "rss",
    "public_web",
    "user_submitted",
    "social_media",
    "unknown",
]

AUTHORITY_LEVELS = [
    "exchange",
    "company",
    "central_government",
    "ministry",
    "national_regulator",
    "provincial_government",
    "provincial_department",
    "municipal_government",
    "municipal_department",
    "international_regulator",
    "central_bank",
    "multilateral_organization",
    "licensed_media",
    "public_media",
    "user",
    "social",
    "unknown",
]

SOURCE_TIERS = ["s", "a", "b", "c", "d", "unknown"]

FUTURE_SOURCE_GROUPS = [
    {
        "group": "国内中央政府和部委",
        "examples": ["国务院", "国家发改委", "工信部", "财政部", "商务部", "国资委"],
        "status": "尚未接入；待技术验证、白名单和法律复核。",
    },
    {
        "group": "国内金融和行业监管机构",
        "examples": ["中国人民银行", "证监会", "金融监管总局", "国家市场监管总局"],
        "status": "尚未接入；未来独立 Provider 与独立领域记录。",
    },
    {
        "group": "统计、海关、能源和药监",
        "examples": ["国家统计局", "海关总署", "国家能源局", "国家药监局"],
        "status": "尚未接入；不得写入 announcement_records。",
    },
    {
        "group": "省级和市级政府",
        "examples": ["省级政府", "市级政府"],
        "status": "尚未接入；未来仅白名单，不做全国市级网站全量扫描。",
    },
    {
        "group": "国际官方机构和多边组织",
        "examples": ["SEC", "Federal Reserve", "ECB", "IMF", "World Bank", "BIS", "OECD"],
        "status": "尚未接入；未来原文与翻译分开。",
    },
    {
        "group": "授权财经媒体",
        "examples": ["Bloomberg", "Reuters", "Financial Times", "Wall Street Journal", "Nikkei Asia"],
        "status": "尚未接入；必须完成商务授权和法律复核后才能开发 Provider。",
    },
    {
        "group": "普通财经媒体、用户提交和社交线索",
        "examples": ["普通财经媒体", "用户提交内容", "社交媒体线索"],
        "status": "尚未自动采集；用户提交不得伪装成官方来源。",
    },
]
