from __future__ import annotations

import json
from datetime import UTC, datetime

from .base import ProviderOutput, ProviderProbe, ProviderRunContext, result_from_http, status_from_http_code
from ..announcement.normalization import build_announcement_record
from ..normalization import symbol_without_exchange
from ..statuses import ProviderStatus


class SseProvider(ProviderProbe):
    name = "sse"
    endpoint = "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do"

    def probe(self, context: ProviderRunContext) -> ProviderOutput:
        output = ProviderOutput()
        params = {
            "jsonCallBack": "",
            "isPagination": "true",
            "pageHelp.pageSize": str(context.max_records),
            "pageHelp.pageNo": "1",
            "pageHelp.beginPage": "1",
            "pageHelp.cacheSize": "1",
            "pageHelp.endPage": "1",
            "productId": symbol_without_exchange(context.symbols[0]) if context.symbols else "",
            "securityType": "0101,120100,020100,020200,120200",
            "reportType": "ALL",
            "beginDate": context.date_from.isoformat(),
            "endDate": context.date_to.isoformat(),
        }
        url = self.endpoint + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        response = context.client.get(url, headers={"Referer": "https://www.sse.com.cn/disclosure/listedinfo/announcement/"})
        if not response.ok or not response.text:
            output.results.append(
                result_from_http(
                    provider=self.name,
                    capability="announcement_list",
                    status=status_from_http_code(response.status_code, response.error),
                    latency_ms=response.elapsed_ms,
                    failure_count=1,
                    error_code=response.error or str(response.status_code),
                    error_summary="SSE list request failed",
                    evidence=[self.endpoint],
                )
            )
            return output
        try:
            payload = json.loads(response.text.strip().strip("();"))
        except json.JSONDecodeError:
            payload = {}
        rows = payload.get("result") or []
        fetched_at = datetime.now(UTC)
        for row in rows[: context.max_records]:
            document_url = row.get("URL")
            if document_url and document_url.startswith("/"):
                document_url = "https://www.sse.com.cn" + document_url
            code = row.get("SECURITY_CODE") or row.get("PRODUCTID")
            record = build_announcement_record(
                provider=self.name,
                provider_id=str(row.get("BULLETINID") or row.get("ROWNUM") or ""),
                title=row.get("TITLE") or row.get("BULLETIN_HEADING") or "",
                published_at=row.get("SSEDATE") or row.get("BULLETIN_DATE"),
                source_page_url="https://www.sse.com.cn/disclosure/listedinfo/announcement/",
                document_url=document_url,
                company_name=row.get("SECURITY_NAME") or row.get("COMPANY_ABBR"),
                symbols=[f"{code}.SH"] if code else [],
                exchange="SH",
                payload=row,
                fetched_at=fetched_at,
            )
            output.announcements.append(record)
            if record.document_url:
                output.pdf_urls.append(record.document_url)
        status = ProviderStatus.PASS if output.announcements else ProviderStatus.DATA_INSUFFICIENT
        output.results.append(
            result_from_http(
                provider=self.name,
                capability="announcement_list",
                status=status,
                latency_ms=response.elapsed_ms,
                success_count=1,
                sample_count=len(output.announcements),
                evidence=[self.endpoint],
                limitations=["Endpoint stability and authorization need manual confirmation."],
                metrics={"supports_date_range": True, "supports_symbol_filter": True, "has_pdf_url": bool(output.pdf_urls)},
            )
        )
        return output
