from html.parser import HTMLParser
from re import sub


class _ReadableTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._title_depth = 0
        self.text_parts: list[str] = []
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        if name in {"script", "style", "noscript", "svg", "canvas", "form", "nav", "footer", "header", "aside"}:
            self._skip_depth += 1
        if name == "title":
            self._title_depth += 1
        if name == "meta":
            key = (attrs_map.get("property") or attrs_map.get("name") or "").lower()
            content = attrs_map.get("content")
            if key and content:
                self.meta[key] = content.strip()

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name in {"script", "style", "noscript", "svg", "canvas", "form", "nav", "footer", "header", "aside"}:
            self._skip_depth = max(0, self._skip_depth - 1)
        if name == "title":
            self._title_depth = max(0, self._title_depth - 1)
        if name in {"p", "div", "section", "article", "br", "li", "h1", "h2", "h3"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._title_depth:
            self.title_parts.append(text)
        if self._skip_depth:
            return
        self.text_parts.append(text)


def normalize_whitespace(value: str) -> str:
    value = sub(r"[ \t\r\f\v]+", " ", value)
    value = sub(r"\n\s*\n+", "\n", value)
    return value.strip()


def extract_text_from_html(html: str) -> tuple[str | None, str, dict[str, str]]:
    parser = _ReadableTextParser()
    parser.feed(html)
    parser.close()
    title = (
        parser.meta.get("og:title")
        or parser.meta.get("twitter:title")
        or normalize_whitespace(" ".join(parser.title_parts))
        or None
    )
    text = normalize_whitespace("\n".join(parser.text_parts))
    return title, text, parser.meta
