from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from .base import ProviderOutput, ProviderProbe, ProviderRunContext, result_from_http, status_from_http_code
from ..date_utils import parse_datetime
from ..news.normalization import build_news_record
from ..statuses import ProviderStatus


RSS_FEEDS = [
    ("gov_cn_rss", "China Government", "rss", "https://www.gov.cn/rss.xml"),
]


class RssProvider(ProviderProbe):
    name = "rss"

    def probe(self, context: ProviderRunContext) -> ProviderOutput:
        output = ProviderOutput()
        for provider_id, source_name, source_type, url in RSS_FEEDS:
            response = context.client.get(url)
            if not response.ok or not response.text:
                output.results.append(
                    result_from_http(
                        provider=provider_id,
                        capability="rss",
                        status=status_from_http_code(response.status_code, response.error),
                        latency_ms=response.elapsed_ms,
                        failure_count=1,
                        error_code=response.error or str(response.status_code),
                        error_summary="RSS feed failed",
                        evidence=[url],
                    )
                )
                continue
            try:
                root = ET.fromstring(response.text)
            except ET.ParseError as exc:
                output.results.append(
                    result_from_http(
                        provider=provider_id,
                        capability="rss",
                        status=ProviderStatus.PARSE_ERROR,
                        latency_ms=response.elapsed_ms,
                        success_count=1,
                        error_code=exc.__class__.__name__,
                        error_summary="RSS XML parse failed",
                        evidence=[url],
                    )
                )
                continue
            items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
            for item in items[: context.max_records]:
                title = item.findtext("title") or item.findtext("{http://www.w3.org/2005/Atom}title") or ""
                link = item.findtext("link") or item.findtext("{http://www.w3.org/2005/Atom}link") or url
                pub_date = item.findtext("pubDate") or item.findtext("published") or item.findtext("{http://www.w3.org/2005/Atom}published")
                output.news.append(
                    build_news_record(
                        provider=provider_id,
                        provider_id=link,
                        title=title,
                        source_name=source_name,
                        published_at=parse_datetime(pub_date).isoformat() if parse_datetime(pub_date) else None,
                        source_url=link,
                        source_type=source_type,
                        extracted_text=item.findtext("description"),
                        known_symbols=context.symbols,
                        payload={"feed": url},
                        fetched_at=datetime.now(UTC),
                    )
                )
            status = ProviderStatus.PASS if output.news else ProviderStatus.DATA_INSUFFICIENT
            output.results.append(
                result_from_http(
                    provider=provider_id,
                    capability="rss",
                    status=status,
                    latency_ms=response.elapsed_ms,
                    success_count=1,
                    sample_count=len(output.news),
                    evidence=[url],
                    limitations=["RSS authorization and commercial reuse require manual review."],
                    metrics={"rss_item_count": len(items)},
                )
            )
        return output
