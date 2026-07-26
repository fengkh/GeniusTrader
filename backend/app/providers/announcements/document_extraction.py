import io
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.url_security import validate_public_content_url
from app.providers.base import provider_http_request
from app.services.html_extraction import normalize_whitespace


@dataclass(frozen=True, slots=True)
class ExtractedAnnouncementDocument:
    text: str
    page_count: int
    character_count: int
    content_type: str | None
    response_bytes: int
    limitations: list[str] = field(default_factory=list)


async def extract_announcement_pdf(
    document_url: str,
    *,
    official_domain: str | None,
    settings: Settings,
) -> ExtractedAnnouncementDocument:
    validated = validate_public_content_url(document_url)
    if official_domain:
        host = validated.host.lower()
        allowed = official_domain.lower()
        if host != allowed and not host.endswith(f".{allowed}"):
            raise AppError(ErrorCode.ANNOUNCEMENT_DOCUMENT_UNAVAILABLE, "公告 PDF 不属于该来源域名", status_code=422)
    response = await provider_http_request(
        "GET",
        validated.normalized_url,
        headers={"Accept": "application/pdf,*/*;q=0.2"},
        timeout_seconds=settings.announcement_request_timeout_seconds,
        max_bytes=settings.announcement_max_pdf_bytes,
    )
    if response.error_code == "MAX_BYTES_EXCEEDED":
        raise AppError(ErrorCode.ANNOUNCEMENT_DOCUMENT_TOO_LARGE, "公告 PDF 超过大小限制", status_code=413)
    if not response.ok:
        raise AppError(ErrorCode.ANNOUNCEMENT_DOCUMENT_UNAVAILABLE, "公告 PDF 暂不可用", status_code=502)
    media_type = (response.content_type or "").split(";", 1)[0].strip().lower()
    if media_type and media_type not in {"application/pdf", "application/octet-stream"}:
        raise AppError(ErrorCode.ANNOUNCEMENT_DOCUMENT_UNAVAILABLE, "公告 PDF 内容类型不可用", status_code=415)
    if not response.content.startswith(b"%PDF"):
        raise AppError(ErrorCode.ANNOUNCEMENT_DOCUMENT_PARSE_FAILED, "公告文件不是有效 PDF", status_code=422)
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise AppError(ErrorCode.ANNOUNCEMENT_DOCUMENT_PARSE_FAILED, "PDF 解析依赖不可用", status_code=500) from exc
    try:
        reader = PdfReader(io.BytesIO(response.content))
    except Exception as exc:
        raise AppError(ErrorCode.ANNOUNCEMENT_DOCUMENT_PARSE_FAILED, "PDF 解析失败", status_code=422) from exc
    page_count = len(reader.pages)
    if page_count > settings.announcement_max_pdf_pages:
        raise AppError(ErrorCode.ANNOUNCEMENT_DOCUMENT_TOO_MANY_PAGES, "公告 PDF 页数超过限制", status_code=413)
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    text = normalize_whitespace("\n".join(parts))
    if len(text) < 20:
        raise AppError(ErrorCode.ANNOUNCEMENT_DOCUMENT_TEXT_UNAVAILABLE, "公告 PDF 未提取到可用文本", status_code=422)
    limitations = [
        "PDF 提取只处理文本层，扫描件、复杂表格和版式可能不完整。",
        "系统不长期保存原始 PDF 文件，也不提供本地 PDF 再下载服务。",
    ]
    if urlsplit(response.url).path.lower().endswith(".pdf") is False:
        limitations.append("最终 URL 未以 .pdf 结尾，已按内容签名识别。")
    return ExtractedAnnouncementDocument(
        text=text,
        page_count=page_count,
        character_count=len(text),
        content_type=response.content_type,
        response_bytes=response.response_bytes,
        limitations=limitations,
    )
