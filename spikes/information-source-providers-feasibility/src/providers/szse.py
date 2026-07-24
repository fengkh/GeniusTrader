from __future__ import annotations

from datetime import UTC, datetime

from .base import ProviderOutput, ProviderProbe, ProviderRunContext, result_from_http, status_from_http_code
from ..announcement.normalization import build_announcement_record
from ..statuses import ProviderStatus


class SzseProvider(ProviderProbe):
    name = "szse"
    endpoint = "https://www.szse.cn/api/disc/announcement/annList"

    def probe(self, context: ProviderRunContext) -> ProviderOutput:
        output = ProviderOutput()
        payload = {
            "seDate": [context.date_from.isoformat(), context.date_to.isoformat()],
            "channelCode": ["listedNotice_disc"],
            "pageSize": context.max_records,
            "pageNum": 1,
        }
        response = context.client.post(
            self.endpoint,
            json_body=payload,
            headers={"Referer": "https://www.szse.cn/disclosure/listed/notice/index.html", "Content-Type": "application/json"},
        )
        if not response.ok or not response.text:
            output.results.append(
                result_from_http(
                    provider=self.name,
                    capability="announcement_list",
                    status=status_from_http_code(response.status_code, response.error),
                    latency_ms=response.elapsed_ms,
                    failure_count=1,
                    error_code=response.error or str(response.status_code),
                    error_summary="SZSE list request failed",
                    evidence=[self.endpoint],
                )
            )
            return output
        try:
            data = response.json() if hasattr(response, "json") else {}
        except Exception:
            import json

            data = json.loads(response.text)
        rows = data.get("data") or data.get("announceList") or []
        fetched_at = datetime.now(UTC)
        for row in rows[: context.max_records]:
            document_url = row.get("attachPath") or row.get("docURL") or row.get("url")
            if document_url and document_url.startswith("/"):
                document_url = "https://disc.static.szse.cn" + document_url
            code = row.get("secCode") or row.get("stockCode")
            record = build_announcement_record(
                provider=self.name,
                provider_id=str(row.get("id") or row.get("announceId") or row.get("attachPath") or ""),
                title=row.get("title") or row.get("announcementTitle") or "",
                published_at=row.get("publishTime") or row.get("publishDate"),
                source_page_url="https://www.szse.cn/disclosure/listed/notice/index.html",
                document_url=document_url,
                company_name=row.get("secName") or row.get("companyName"),
                symbols=[f"{code}.SZ"] if code else [],
                exchange="SZ",
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
                limitations=["Endpoint and automated access permission require manual review."],
                metrics={"supports_date_range": True, "supports_symbol_filter": "unknown", "has_pdf_url": bool(output.pdf_urls)},
            )
        )
        return output
