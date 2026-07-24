# Information Source Providers Feasibility Spike

This spike probes public announcement and financial/news sources for GeniusTrader.
It is intentionally isolated from the production backend and must not write to
`information_items`, `business_events`, `notifications`, or any formal business
table.

## Scope

- Probe announcement sources: CNINFO, SSE, SZSE, BSE.
- Probe public news sources: regulator/exchange public pages and RSS/Atom feeds.
- Normalize small samples into spike-only records.
- Evaluate PDF availability, incremental cursor options, deduplication, source
  traceability, authorization uncertainty, and 10/50/200 symbol cost.
- Generate ignored local reports under `output/`.

## Explicit Non-Goals

- No production provider implementation.
- No scheduler, queue, Redis, Celery, Kafka, Docker, WeChat, market data, or
  valuation work.
- No login, user cookies, proxy, CAPTCHA bypass, browser automation, or pressure
  testing.
- No storage of full private content, credentials, cookies, tokens, or API keys.

## Run

```powershell
python -m pytest spikes/information-source-providers-feasibility/tests -q
python -m compileall spikes/information-source-providers-feasibility/src
python spikes/information-source-providers-feasibility/run_spike.py --max-records 8 --request-delay 1.0
```

Use conservative defaults. The real network run prints the provider set, date
range, symbol count, record cap, and request delay before making requests.

Reports are written to `spikes/information-source-providers-feasibility/output/`,
which is ignored by Git.
