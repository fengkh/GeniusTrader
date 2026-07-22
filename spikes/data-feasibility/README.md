# GeniusTrader Data Feasibility Spike

This is an isolated spike for validating Tushare as a candidate data provider. It is not a backend service, does not initialize a database, and does not connect the existing Mock frontend to real data.

## Scope

The spike checks whether a local `TUSHARE_TOKEN` can access the data needed by the V1 product baseline:

- stock metadata and listing status;
- daily OHLCV, daily basic metrics and adjustment factors;
- suspend/resume events;
- CSI 300 and ChiNext index daily data;
- Shenwan industry membership through `index_member_all`;
- Shenwan industry daily quote through the official `sw_daily` interface name;
- current-day minute data through `rt_min_daily` only during the supported time window;
- announcements through `anns_d`;
- one optional concept/member probe through `tdx_member`;
- one optional small news permission probe.

Tushare remains a candidate provider only. Reports must be reviewed before any formal provider decision.

## Token Safety

- The token is read only from `TUSHARE_TOKEN`.
- The code calls `tushare.pro_api(token)` and does not call persistent token storage helpers.
- The token is never printed intentionally.
- Reports are checked after writing to make sure the full token does not appear.
- Do not create `.env` with real values in this directory.

## Local Environment

From the repository root:

```powershell
python -m venv .venv-data-spike
.\.venv-data-spike\Scripts\python.exe -m pip install -r spikes\data-feasibility\requirements.txt
```

On Linux/macOS:

```bash
python -m venv .venv-data-spike
./.venv-data-spike/bin/python -m pip install -r spikes/data-feasibility/requirements.txt
```

## Run Tests

```powershell
.\.venv-data-spike\Scripts\python.exe -m pytest spikes\data-feasibility\tests
.\.venv-data-spike\Scripts\python.exe -m compileall spikes\data-feasibility
```

## Run Real Spike

Set the token only in your local shell:

```powershell
$env:TUSHARE_TOKEN = "your-local-token"
.\.venv-data-spike\Scripts\python.exe spikes\data-feasibility\run_spike.py
```

Useful options:

```powershell
.\.venv-data-spike\Scripts\python.exe spikes\data-feasibility\run_spike.py --symbols 600519.SH,000001.SZ --days 220 --percentile-window 120
.\.venv-data-spike\Scripts\python.exe spikes\data-feasibility\run_spike.py --skip-optional
.\.venv-data-spike\Scripts\python.exe spikes\data-feasibility\run_spike.py --output-dir spikes\data-feasibility\output
```

## Output

The default output directory is git-ignored:

```text
spikes/data-feasibility/output/
  capability_report.json
  capability_report.md
  metrics_report.json
  metrics_report.md
  data_quality_report.json
  data_quality_report.md
  sample_summary.csv
```

The reports store capability records, metric results and quality checks. They do not store full raw market datasets or full news/announcement bodies.

## Metric Formula Notes

- 5/10/20 day returns use locally calculated qfq close.
- QFQ uses the latest valid adjustment factor as the normalization base.
- Distance to 20-day high is `latest qfq close / max(last 20 qfq high) - 1`.
- Historical percentiles use the latest value's percentile rank in the latest valid trading-day window.
- Close position is `(close - low) / (high - low)` and is missing when `high == low`.
- Relative index strength is stock 5-day return minus benchmark index 5-day return.
- Relative industry strength requires Shenwan industry daily data and is missing if `sw_daily` is unavailable.
- Max intraday drawdown requires real minute close data from `rt_min_daily`; daily high/low must not be used as a substitute.
