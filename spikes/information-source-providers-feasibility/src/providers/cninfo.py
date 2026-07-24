from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from .base import ProviderOutput, ProviderProbe, ProviderRunContext, result_from_http, status_from_http_code
from ..announcement.normalization import build_announcement_record
from ..normalization import symbol_without_exchange
from ..statuses import ProviderStatus


class CninfoProvider(ProviderProbe):
    name = "cninfo"
    endpoint = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    static_base = "http://static.cninfo.com.cn/"

    def probe(self, context: ProviderRunContext) -> ProviderOutput:
        output = ProviderOutput()
        data = {
            "pageNum": 1,
            "pageSize": context.max_records,
            "column": "szse",
            "tabName": "fulltext",
            "plate": "",
            "stock": "",
            "searchkey": "",
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": f"{context.date_from.isoformat()}~{context.date_to.isoformat()}",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        if context.symbols:
            data["stock"] = ",".join(symbol_without_exchange(symbol) for symbol in context.symbols[:5])
        headers = {
            "Referer": "http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        response = context.client.post(self.endpoint, data=data, headers=headers)
        if not response.ok or not response.text:
            output.results.append(
                result_from_http(
                    provider=self.name,
                    capability="announcement_list",
                    status=status_from_http_code(response.status_code, response.error),
                    latency_ms=response.elapsed_ms,
                    failure_count=1,
                    error_code=response.error or str(response.status_code),
                    error_summary="CNINFO list request failed",
                    evidence=[self.endpoint],
                )
            )
            return output
        payload: dict[str, Any] = json.loads(response.text)
        rows = payload.get("announcements") or []
        request_count = 1
        success_count = 1 if response.ok else 0
        latency_ms = response.elapsed_ms
        if not rows and data.get("stock"):
            fallback_data = {**data, "stock": ""}
            fallback_response = context.client.post(self.endpoint, data=fallback_data, headers=headers)
            request_count += 1
            latency_ms += fallback_response.elapsed_ms
            if fallback_response.ok and fallback_response.text:
                success_count += 1
                try:
                    fallback_payload: dict[str, Any] = json.loads(fallback_response.text)
                    fallback_rows = fallback_payload.get("announcements") or []
                    if fallback_rows:
                        rows = fallback_rows
                except Exception:
                    pass
        fetched_at = datetime.now(UTC)
        for row in rows[: context.max_records]:
            adjunct = row.get("adjunctUrl")
            document_url = f"{self.static_base}{adjunct}" if adjunct else None
            sec_code = row.get("secCode")
            exchange = "SZ" if row.get("orgId", "").startswith("gssz") else "SH" if row.get("orgId", "").startswith("gssh") else None
            symbol = f"{sec_code}.{exchange}" if sec_code and exchange else sec_code
            record = build_announcement_record(
                provider=self.name,
                provider_id=str(row.get("announcementId") or ""),
                title=row.get("announcementTitle") or "",
                published_at=row.get("announcementTime"),
                source_page_url="http://www.cninfo.com.cn/new/disclosure/detail",
                document_url=document_url,
                company_name=row.get("secName"),
                symbols=[symbol] if symbol else [],
                exchange=exchange,
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
                latency_ms=latency_ms,
                request_count=request_count,
                success_count=success_count,
                sample_count=len(output.announcements),
                evidence=[self.endpoint, "announcements JSON field"],
                limitations=["Authorization and redistribution terms require manual review."],
                metrics={"has_provider_id": True, "has_pdf_url": bool(output.pdf_urls), "supports_date_range": True, "supports_symbol_filter": True},
            )
        )
        return output
