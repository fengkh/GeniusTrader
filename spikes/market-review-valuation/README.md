# Market Review and Valuation Feasibility Spike

This isolated spike validates two product capabilities:

- whole-market daily review with hot boards, hot stocks inside boards and next-day observation candidates;
- stock valuation center with program-selected valuation methods.

It is not a formal backend, not a database, not a trading system and not a provider selection decision.

## Boundary

- No brokerage account, order placement, position sizing, target-price command or return guarantee.
- No real AI calls. AI may only explain structured program output in the future.
- No provider is hard-coded as the final V1 supplier.
- Full-market conclusions must distinguish real full snapshots from limited deterministic samples.
- Valuation intervals are model estimates, not factual value or investment advice.
- Program valuation methods include stable PE, PB-ROE, PS, dividend yield, normalized cycle and DCF data-sufficiency feasibility.

## Run

```powershell
python run_spike.py --max-boards 5 --max-stocks-per-board 5 --request-interval 0.2
```

Use `--skip-network` for offline report generation with deterministic formula samples. Offline samples are not proof that real providers can support production data.

## Outputs

The script writes ignored local reports to `output/`:

- `market_capability_report.md`
- `market_review_report.md`
- `board_ranking_report.md`
- `stock_ranking_report.md`
- `valuation_capability_report.md`
- `valuation_report.md`
- `provider_gap_report.md`
- `run_manifest.json`
- `market_review.json`
- `valuations.json`
