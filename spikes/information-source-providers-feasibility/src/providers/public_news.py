from __future__ import annotations

import re
from datetime import UTC, datetime

from .base import ProviderOutput, ProviderProbe, ProviderRunContext, result_from_http, status_from_http_code
from ..news.extraction import extract_text_from_html, extract_title_from_html
from ..news.normalization import build_news_record
from ..statuses import ProviderStatus
from ..url_utils import normalize_url


NEWS_PAGES = [
    ("csrc_news", "CSRC", "regulator_news", "https://www.csrc.gov.cn/csrc/c100028/common_list.shtml"),
    ("sse_news", "SSE", "exchange_news", "https://www.sse.com.cn/aboutus/mediacenter/hotandd/"),
    ("sasac_news", "SASAC", "regulator_news", "https://www.sasac.gov.cn/n2588025/n2588124/index.html"),
]


class PublicNewsProvider(ProviderProbe):
    name = "public_news"

    def probe(self, context: ProviderRunContext) -> ProviderOutput:
        output = ProviderOutput()
        for provider_id, source_name, source_type, url in NEWS_PAGES:
            response = context.client.get(url)
            status = status_from_http_code(response.status_code, response.error)
            if not response.ok or not response.text:
                output.results.append(
                    result_from_http(
                        provider=provider_id,
                        capability="news_list",
                        status=status,
                        latency_ms=response.elapsed_ms,
                        failure_count=1,
                        error_code=response.error or str(response.status_code),
                        error_summary="public news page failed",
                        evidence=[url],
                    )
                )
                continue
            title = extract_title_from_html(response.text) or f"{source_name} public news page"
            text = extract_text_from_html(response.text)
            links = re.findall(r'href=["\\\']([^"\\\']+)["\\\']', response.text, flags=re.I)
            canonical = normalize_url(url)
            output.news.append(
                build_news_record(
                    provider=provider_id,
                    provider_id=canonical,
                    title=title,
                    source_name=source_name,
                    published_at=None,
                    source_url=canonical,
                    source_type=source_type,
                    extracted_text=text,
                    known_symbols=context.symbols,
                    payload={"link_count": len(links)},
                    fetched_at=datetime.now(UTC),
                )
            )
            output.results.append(
                result_from_http(
                    provider=provider_id,
                    capability="news_list",
                    status=ProviderStatus.PARTIAL,
                    latency_ms=response.elapsed_ms,
                    success_count=1,
                    sample_count=1,
                    evidence=[url],
                    limitations=["List page accessibility verified; item-level stable API and redistribution permission remain unclear."],
                    metrics={"link_count": len(links), "extracted_text_chars": len(text)},
                )
            )
        return output
