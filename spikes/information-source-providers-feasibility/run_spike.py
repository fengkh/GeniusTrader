from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.announcement.incremental import build_cursor
from src.announcement.pdf_probe import probe_pdf
from src.config import DEFAULT_SYMBOLS, SpikeConfig, default_date_window, parse_symbols
from src.dedup.event_grouping import group_events
from src.dedup.exact import exact_deduplicate
from src.dedup.near_duplicate import near_duplicate_pairs
from src.http_client import SpikeHttpClient
from src.providers.base import ProviderRunContext
from src.providers.bse import BseProvider
from src.providers.cninfo import CninfoProvider
from src.providers.public_news import PublicNewsProvider
from src.providers.rss import RssProvider
from src.providers.sse import SseProvider
from src.providers.szse import SzseProvider
from src.report_writer import write_json, write_text
from src.reports import (
    announcement_report,
    capability_report,
    compliance_report,
    dedup_report,
    incremental_report,
    news_report,
    recommendation_report,
)
from src.metrics.coverage import completeness_summary, missing_field_counts
from src.metrics.freshness import detect_future_timestamps, freshness_summary
from src.metrics.performance import latency_summary
from src.metrics.stability import stability_summary


PROVIDERS = {
    "cninfo": CninfoProvider,
    "sse": SseProvider,
    "szse": SzseProvider,
    "bse": BseProvider,
    "public_news": PublicNewsProvider,
    "rss": RssProvider,
}

PROVIDER_CAPABILITY_GROUPS = {
    "cninfo": "announcements",
    "sse": "announcements",
    "szse": "announcements",
    "bse": "announcements",
    "public_news": "news",
    "rss": "news",
}


def parse_args() -> argparse.Namespace:
    date_from, date_to = default_date_window(30)
    parser = argparse.ArgumentParser(description="Probe public announcement and news providers with conservative limits.")
    parser.add_argument("--providers", default="cninfo,sse,szse,bse,public_news,rss")
    parser.add_argument("--capabilities", default="announcements,news,pdf")
    parser.add_argument("--date-from", default=date_from.isoformat())
    parser.add_argument("--date-to", default=date_to.isoformat())
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--max-records", type=int, default=8)
    parser.add_argument("--max-requests", type=int, default=40)
    parser.add_argument("--request-delay", type=float, default=1.0)
    parser.add_argument("--output-dir", default=str(ROOT / "output"))
    parser.add_argument("--skip-pdf", action="store_true")
    parser.add_argument("--skip-news", action="store_true")
    parser.add_argument("--skip-announcements", action="store_true")
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> SpikeConfig:
    return SpikeConfig(
        providers=[item.strip() for item in args.providers.split(",") if item.strip()],
        capabilities=[item.strip() for item in args.capabilities.split(",") if item.strip()],
        date_from=date.fromisoformat(args.date_from),
        date_to=date.fromisoformat(args.date_to),
        symbols=parse_symbols(args.symbols),
        max_records=max(1, min(args.max_records, 50)),
        max_requests=max(1, min(args.max_requests, 100)),
        request_delay=max(0.2, args.request_delay),
        output_dir=Path(args.output_dir),
        skip_pdf=args.skip_pdf,
        skip_news=args.skip_news,
        skip_announcements=args.skip_announcements,
    )


def estimate_cost(symbol_counts: list[int], provider_result_count: int, avg_latency_ms: float | None) -> list[dict]:
    estimates: list[dict] = []
    avg_latency_ms = avg_latency_ms or 1500
    for count in symbol_counts:
        estimates.append(
            {
                "symbol_count": count,
                "mode_a_per_symbol_daily_requests": count,
                "mode_a_7_day_requests": count * 7,
                "mode_a_estimated_latency_seconds": round(count * avg_latency_ms / 1000, 2),
                "mode_b_market_date_requests": max(2, provider_result_count),
                "mode_c_hybrid_requests": max(2, provider_result_count) + min(20, max(1, count // 10)),
                "recommendation": "prefer market/date batch plus targeted symbol backfill",
            }
        )
    return estimates


def write_reports(config: SpikeConfig, results: list[dict], announcements: list[dict], news: list[dict], pdf_results: list[dict], started_at: datetime, elapsed_seconds: float, total_http_requests: int) -> None:
    output_dir = config.output_dir
    exact_unique = exact_deduplicate([*announcements, *news])
    near_pairs = near_duplicate_pairs([*announcements, *news])
    event_groups = group_events([*announcements, *news])
    cursors = []
    for provider in sorted({record.get("provider") for record in announcements + news if record.get("provider")}):
        provider_records = [record for record in announcements + news if record.get("provider") == provider]
        if provider_records:
            cursors.append(build_cursor(provider, "announcement_or_news", provider_records).to_dict())
    perf = latency_summary(results)
    raw_metrics = {
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "elapsed_seconds": round(elapsed_seconds, 2),
        "network_environment": "local machine, public internet if available, no login, no proxy, no browser automation",
        "providers": config.providers,
        "date_from": config.date_from.isoformat(),
        "date_to": config.date_to.isoformat(),
        "symbols": config.symbols,
        "request_delay": config.request_delay,
        "max_records": config.max_records,
        "total_http_requests": total_http_requests,
        "result_count": len(results),
        "announcement_count": len(announcements),
        "news_count": len(news),
        "pdf_probe_count": len(pdf_results),
        "deduplicated_count": len(exact_unique),
        "near_duplicate_pair_count": len(near_pairs),
        "event_group_count": len(event_groups),
        "stability": stability_summary(results),
        "latency": perf,
        "announcement_completeness": completeness_summary(announcements),
        "announcement_missing_fields": missing_field_counts(announcements),
        "news_completeness": completeness_summary(news),
        "news_missing_fields": missing_field_counts(news),
        "announcement_freshness": freshness_summary(announcements),
        "news_freshness": freshness_summary(news),
        "future_timestamp_items": detect_future_timestamps([*announcements, *news], datetime.now(UTC)),
        "cost_estimates": estimate_cost([10, 50, 200], len(results), perf.get("avg_ms")),
    }
    write_json(output_dir / "provider_capability.json", {"results": results})
    write_text(output_dir / "provider_capability_report.md", capability_report.render(results))
    write_json(output_dir / "announcement_samples.json", announcements)
    write_text(output_dir / "announcement_feasibility_report.md", announcement_report.render(announcements, results))
    write_json(output_dir / "news_samples.json", news)
    write_text(output_dir / "news_feasibility_report.md", news_report.render(news, results))
    write_json(output_dir / "pdf_samples.json", pdf_results)
    write_text(output_dir / "pdf_feasibility_report.md", render_pdf_report(pdf_results))
    write_json(output_dir / "incremental_cursors.json", cursors)
    write_text(output_dir / "incremental_sync_report.md", incremental_report.render(cursors))
    write_json(output_dir / "deduplication.json", {"exact_unique_count": len(exact_unique), "near_pairs": near_pairs, "event_groups": event_groups})
    write_text(output_dir / "deduplication_report.md", dedup_report.render(len(exact_unique), near_pairs, event_groups))
    write_text(output_dir / "performance_report.md", render_performance_report(raw_metrics))
    write_text(output_dir / "compliance_and_authorization_report.md", compliance_report.render(results))
    write_text(output_dir / "provider_recommendation.md", recommendation_report.render(results))
    write_json(output_dir / "raw_metrics.json", raw_metrics)


def render_pdf_report(pdf_results: list[dict]) -> str:
    ok = sum(1 for item in pdf_results if item.get("status") in {"PASS", "PARTIAL"})
    text_like = sum(1 for item in pdf_results if (item.get("extractable_text_chars") or 0) >= 50)
    scan_like = sum(1 for item in pdf_results if item.get("needs_ocr") is True)
    return "\n".join(
        [
            "# PDF Feasibility Report",
            "",
            f"- PDF samples: {len(pdf_results)}",
            f"- Download or partial success: {ok}",
            f"- Text-like PDFs: {text_like}",
            f"- Scan-like or OCR-needed PDFs: {scan_like}",
            "",
            "PDF availability does not imply permission to store or redistribute full documents.",
        ]
    ) + "\n"


def render_performance_report(metrics: dict) -> str:
    return "\n".join(
        [
            "# Performance Report",
            "",
            f"- Total elapsed seconds: {metrics['elapsed_seconds']}",
            f"- Stability: `{metrics['stability']}`",
            f"- Latency: `{metrics['latency']}`",
            "",
            "## 10/50/200 Symbol Cost Estimate",
            "",
            "| Symbols | Mode A Daily Requests | Mode A 7-Day Requests | Mode B Requests | Mode C Requests |",
            "| ---: | ---: | ---: | ---: | ---: |",
            *[
                f"| {item['symbol_count']} | {item['mode_a_per_symbol_daily_requests']} | {item['mode_a_7_day_requests']} | {item['mode_b_market_date_requests']} | {item['mode_c_hybrid_requests']} |"
                for item in metrics["cost_estimates"]
            ],
        ]
    ) + "\n"


def main() -> int:
    args = parse_args()
    config = build_config(args)
    print("GeniusTrader information source provider spike")
    print(f"providers={config.providers}")
    print(f"date_range={config.date_from.isoformat()}..{config.date_to.isoformat()}")
    print(f"symbol_count={len(config.symbols)}")
    print(f"max_records={config.max_records}")
    print(f"max_requests={config.max_requests}")
    print(f"request_delay={config.request_delay}")
    print("secrets_or_tokens=not_used")
    client = SpikeHttpClient(timeout=12, max_bytes=2_000_000, delay_seconds=config.request_delay)
    context = ProviderRunContext(
        client=client,
        date_from=config.date_from,
        date_to=config.date_to,
        symbols=config.symbols,
        max_records=config.max_records,
        skip_pdf=config.skip_pdf,
    )
    started = datetime.now(UTC)
    started_perf = time.perf_counter()
    provider_results = []
    announcements = []
    news = []
    pdf_urls: list[str] = []
    for provider_name in config.providers:
        if client.request_count >= config.max_requests:
            break
        provider_class = PROVIDERS.get(provider_name)
        if not provider_class:
            print(f"skip_unknown_provider={provider_name}")
            continue
        capability_group = PROVIDER_CAPABILITY_GROUPS.get(provider_name)
        if capability_group == "announcements" and (config.skip_announcements or "announcements" not in config.capabilities):
            print(f"skip_announcements_provider={provider_name}")
            continue
        if capability_group == "news" and (config.skip_news or "news" not in config.capabilities):
            print(f"skip_news_provider={provider_name}")
            continue
        provider = provider_class()
        output = provider.probe(context)
        provider_results.extend(output.results)
        announcements.extend(record.to_dict() for record in output.announcements)
        news.extend(record.to_dict() for record in output.news)
        pdf_urls.extend(output.pdf_urls)
    pdf_results = []
    if not config.skip_pdf and "pdf" in config.capabilities:
        for url in list(dict.fromkeys(pdf_urls))[: min(6, config.max_records)]:
            if client.request_count >= config.max_requests:
                break
            pdf_results.append(probe_pdf(client, url))
    elapsed = time.perf_counter() - started_perf
    result_dicts = [result.to_dict() for result in provider_results]
    write_reports(config, result_dicts, announcements, news, pdf_results, started, elapsed, client.request_count)
    stability = stability_summary(result_dicts)
    print(f"total_requests={client.request_count}")
    print(f"success_count={stability['success_count']}")
    print(f"failure_count={stability['failure_count']}")
    print(f"rate_limited={stability['rate_limited_count']}")
    print(f"access_denied={stability['access_denied_count']}")
    print(f"timeouts={stability['timeout_count']}")
    print(f"record_count={len(announcements) + len(news)}")
    print(f"deduplicated_count={len(exact_deduplicate([*announcements, *news]))}")
    print(f"pdf_probe_count={len(pdf_results)}")
    print(f"output_dir={config.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
