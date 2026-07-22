# GeniusTrader Free Data Provider Feasibility Spike

This is an isolated feasibility spike for AKShare, efinance and BaoStock. It does not select a final data provider and does not connect to the Mock frontend, backend, database, authentication, task queues or real AI services.

## Scope

- Validate free candidate provider capabilities for personal MVP research.
- Normalize provider fields into GeniusTrader internal draft fields.
- Record unsupported APIs, schema changes, upstream failures, unit uncertainty and fallback suggestions.
- Compare overlapping daily data across providers after unit normalization.
- Reuse the same `gt-metrics-v0.1` metric formulas as the existing Tushare spike.

## Local Setup

```powershell
python -m venv .venv-free-data-spike
.\.venv-free-data-spike\Scripts\python.exe -m pip install -r spikes\free-data-feasibility\requirements.txt
```

## Run

```powershell
.\.venv-free-data-spike\Scripts\python.exe spikes\free-data-feasibility\run_spike.py --providers akshare,efinance,baostock --symbols 600519,000001,300750,688981 --days 220 --percentile-window 120 --stability-runs 3 --request-interval 1.0
```

Optional flags:

- `--skip-minute`
- `--skip-boards`
- `--skip-announcements`
- `--output-dir spikes/free-data-feasibility/output`
- `--save-samples`

The default run does not save large raw market datasets. Output reports are written to `spikes/free-data-feasibility/output/`, which is ignored by Git.

## Safety Boundaries

- No token or account is required for these free-provider probes.
- No proxy pool, cookie pool, CAPTCHA bypass or internal upstream URL copying is used.
- Python library licenses are not the same as data redistribution rights. Commercial launch still requires supplier licensing and legal review.
- Empty, stale or failed upstream results are reported as such and are never fabricated.
