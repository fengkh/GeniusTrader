# GeniusTrader Daily Pilot Report Example

> This is a local-only template. Save filled reports under `tmp/pilot/`. Do not commit filled reports.

## Basic Info

- Report date:
- Operator:
- Environment:
- Branch:
- Backend migration:
- Frontend URL:
- Backend URL:

## Credential Boundary

- `.local/market-data.env` present: yes/no
- Tushare Token printed anywhere: no
- Real Provider smoke status: pass / partial / failed / blocked_by_local_credential
- Authorization status shown by system:

## Watchlist Scope

- User:
- Watchlist stock count:
- Explicit stock IDs used: yes/no
- Full-market sync attempted: no

## Market Data Smoke

- Provider:
- Latest completed trade date:
- Symbols requested:
- Symbols returned:
- Field coverage summary:
- Unit normalization checked: yes/no
- Network or permission errors:
- Data persisted: yes/no

## Daily Workflow

- `/today` loaded: pass/fail
- `/watchlist` loaded: pass/fail
- `/watchlist/[stockId]` loaded: pass/fail
- `/settings/market-data` loaded: pass/fail
- Announcement candidate workflow checked: pass/fail/not run
- User-triggered AI analysis checked: pass/fail/not run
- Daily review checked: pass/fail/not run
- Notification checked: pass/fail/not run

## Degradation

- Missing quote state:
- Partial quote state:
- Stale quote state:
- Provider failure state:
- AI failure state:
- Empty watchlist state:

## Security

- API Key/Token printed: no
- Cookie/Session printed: no
- Database password printed: no
- Filled report committed: no

## Issues

- P0:
- P1:
- P2:

## Final Decision

- Ready for next daily pilot: yes/no
- Blocks:
- Follow-up owner:
