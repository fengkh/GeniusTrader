from __future__ import annotations

import re
import unicodedata


SYMBOL_RE = re.compile(r"^(?P<code>\d{6})(?:\.(?P<exchange>SH|SZ|BJ))?$", re.I)


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value)
    return " ".join(text.replace("\u3000", " ").split())


def normalize_title(value: str | None) -> str:
    text = normalize_text(value)
    text = re.sub(r"[【】\\[\\]（）()]", " ", text)
    return " ".join(text.split()).lower()


def normalize_symbol(value: str) -> str:
    text = value.strip().upper()
    match = SYMBOL_RE.match(text)
    if not match:
        raise ValueError(f"invalid A-share symbol: {value}")
    code = match.group("code")
    exchange = match.group("exchange")
    if not exchange:
        if code.startswith(("6", "9")):
            exchange = "SH"
        elif code.startswith(("0", "2", "3")):
            exchange = "SZ"
        elif code.startswith(("4", "8")):
            exchange = "BJ"
        else:
            raise ValueError(f"cannot infer exchange for symbol: {value}")
    return f"{code}.{exchange}"


def symbol_without_exchange(symbol: str) -> str:
    return normalize_symbol(symbol).split(".")[0]
