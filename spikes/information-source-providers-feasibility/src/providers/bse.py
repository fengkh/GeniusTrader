from __future__ import annotations

import re
from datetime import UTC, datetime

from .base import ProviderOutput, ProviderProbe, ProviderRunContext, result_from_http, status_from_http_code
from ..announcement.normalization import build_announcement_record
from ..news.extraction import extract_text_from_html
from ..statuses import ProviderStatus
from ..url_utils import normalize_url


class BseProvider(ProviderProbe):
    name = "bse"
    page_url = "https://www.bse.cn/disclosure/announcement.html"

    def probe(self, context: ProviderRunContext) -> ProviderOutput:
        output = ProviderOutput()
        response = context.client.get(self.page_url)
        if not response.ok or not response.text:
            output.results.append(
                result_from_http(
                    provider=self.name,
                    capability="announcement_list",
                    status=status_from_http_code(response.status_code, response.error),
                    latency_ms=response.elapsed_ms,
                    failure_count=1,
                    error_code=response.error or str(response.status_code),
                    error_summary="BSE public announcement page failed",
                    evidence=[self.page_url],
                )
            )
            return output
        links = re.findall(r'href=["\\\']([^"\\\']+\\.pdf[^"\\\']*)["\\\']', response.text, flags=re.I)
        fetched_at = datetime.now(UTC)
        for index, href in enumerate(links[: context.max_records]):
            url = href if href.startswith("http") else "https://www.bse.cn" + href
            output.announcements.append(
                build_announcement_record(
                    provider=self.name,
                    provider_id=f"page-link-{index}",
                    title=f"BSE PDF link sample {index + 1}",
                    published_at=None,
                    source_page_url=self.page_url,
                    document_url=normalize_url(url),
                    company_name=None,
                    symbols=[],
                    exchange="BJ",
                    payload={"href": href},
                    fetched_at=fetched_at,
                )
            )
            output.pdf_urls.append(url)
        text_len = len(extract_text_from_html(response.text))
        status = ProviderStatus.PARTIAL if response.ok else ProviderStatus.NETWORK_ERROR
        if not output.announcements:
            status = ProviderStatus.DATA_INSUFFICIENT
        output.results.append(
            result_from_http(
                provider=self.name,
                capability="announcement_list",
                status=status,
                latency_ms=response.elapsed_ms,
                success_count=1,
                sample_count=len(output.announcements),
                evidence=[self.page_url],
                limitations=["Only public page accessibility is verified when dynamic API cannot be confirmed.", "Stock relation fields are not confirmed."],
                metrics={"page_text_chars": text_len, "pdf_link_count": len(output.pdf_urls), "supports_incremental": "unclear"},
            )
        )
        return output
