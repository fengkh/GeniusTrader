import hashlib
import json
import re
from datetime import date, datetime
from typing import Any

from app.core.time import utc_now

SUPPORTED_EXCHANGES = {"SH", "SZ", "BJ"}
SUPPORTED_SECURITY_TYPES = {"common_stock"}
SEARCHABLE_LISTING_STATUSES = {"active", "suspended", "risk_warning"}

STATUS_ALIASES = {
    "1": "active",
    "上市": "active",
    "正常上市": "active",
    "A": "active",
    "L": "active",
    "listed": "active",
    "active": "active",
    "暂停上市": "suspended",
    "停牌": "suspended",
    "0": "suspended",
    "suspended": "suspended",
    "风险警示": "risk_warning",
    "ST": "risk_warning",
    "*ST": "risk_warning",
    "退市整理": "delisting_period",
    "delisting_period": "delisting_period",
    "终止上市": "delisted",
    "退市": "delisted",
    "delisted": "delisted",
}

BOARD_ALIASES = {
    "主板": "main_board",
    "沪市主板": "main_board",
    "深市主板": "main_board",
    "科创板": "star_board",
    "创业板": "chinext",
    "北交所": "bse",
    "北京证券交易所": "bse",
}

PINYIN_OVERRIDES = {
    "贵州茅台": ("guizhoumaotai", "gzmt"),
    "宁德时代": ("ningdeshidai", "ndsd"),
    "平安银行": ("pinganyinhang", "payh"),
    "中芯国际": ("zhongxinguoji", "zxgj"),
    "晶合集成": ("jinghejicheng", "jhjc"),
    "贝特瑞": ("beiterui", "btr"),
}


def normalize_code(value: Any) -> str | None:
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".")[-1] if text.lower().startswith(("sh.", "sz.", "bj.")) else text.split(".", 1)[0]
    digits = re.sub(r"\D", "", text)
    if len(digits) != 6:
        return None
    return digits


def normalize_exchange(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    mapping = {
        "SH": "SH",
        "SSE": "SH",
        "XSHG": "SH",
        "上海": "SH",
        "上海证券交易所": "SH",
        "SZ": "SZ",
        "SZSE": "SZ",
        "XSHE": "SZ",
        "深圳": "SZ",
        "深圳证券交易所": "SZ",
        "BJ": "BJ",
        "BSE": "BJ",
        "北交所": "BJ",
        "北京证券交易所": "BJ",
    }
    return mapping.get(text)


def normalize_symbol(code: str, exchange: str) -> str:
    return f"{code}.{exchange}"


def normalize_board(value: Any, *, exchange: str, code: str) -> str:
    text = str(value or "").strip()
    if text in BOARD_ALIASES:
        return BOARD_ALIASES[text]
    if exchange == "SH" and code.startswith("688"):
        return "star_board"
    if exchange == "SZ" and code.startswith("300"):
        return "chinext"
    if exchange == "BJ":
        return "bse"
    return "main_board"


def normalize_listing_status(value: Any, *, short_name: str | None = None) -> str:
    text = str(value or "").strip()
    if short_name and short_name.upper().startswith(("*ST", "ST")):
        return "risk_warning"
    return STATUS_ALIASES.get(text, STATUS_ALIASES.get(text.upper(), "unknown"))


def normalize_security_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"", "a", "a股", "ashare", "common_stock", "stock", "股票", "普通股"}:
        return "common_stock"
    return text


def parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    text = text.split(" ", 1)[0].replace("/", "-")
    if re.fullmatch(r"\d{8}", text):
        text = f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    elif re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", text):
        year, month, day = text.split("-")
        text = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def metadata_hash(payload: dict[str, Any]) -> str:
    dumped = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def completeness_for(record: dict[str, Any], required_fields: list[str]) -> tuple[str, list[str]]:
    missing = [field for field in required_fields if not record.get(field)]
    if not missing:
        return "complete", []
    if "code" in missing or "exchange" in missing or "short_name" in missing:
        return "insufficient", missing
    return "usable", missing


def pinyin_fields(short_name: str, raw: dict[str, Any] | None = None) -> tuple[str | None, str | None]:
    raw = raw or {}
    pinyin = _first_non_empty(raw, ["pinyin", "拼音", "QP", "fullPinyin"])
    initials = _first_non_empty(raw, ["pinyin_initials", "拼音缩写", "JP", "initials"])
    if pinyin or initials:
        return _compact_ascii(pinyin), _compact_ascii(initials)
    if short_name in PINYIN_OVERRIDES:
        return PINYIN_OVERRIDES[short_name]
    return None, None


def fetched_at_now() -> datetime:
    return utc_now()


def first_non_empty(raw: dict[str, Any], keys: list[str]) -> str | None:
    return _first_non_empty(raw, keys)


def _first_non_empty(raw: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = raw.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _compact_ascii(value: str | None) -> str | None:
    if not value:
        return None
    compacted = re.sub(r"[^0-9A-Za-z]", "", value).lower()
    return compacted or None
