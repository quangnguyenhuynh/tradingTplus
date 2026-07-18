# GitHub Actions workflows

Automation for tests and explicit Trading T+ pipelines.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Current workflows

| File | Trigger | Current command |
| --- | --- | --- |
| `tests.yml` | Pull requests and pushes to `dev` | `python -m pytest -q` on Python 3.11. |
| `daily.yml` | Daily at 00:00 UTC (07:00 Vietnam time) and manual dispatch | `python main.py daily`. |
| `eod.yml` | Weekdays at 09:30 UTC (16:30 Vietnam time) and manual dispatch | `python main.py eod [date]`. |
| `features.yml` | Manual dispatch only | Explicit `python main.py features ...`. |

## Operational notes

- `daily.yml` is scheduled every calendar day; application date resolution and empty SSI responses must still be handled safely.
- `eod.yml` orchestrates daily ingest, intraday ingest, and completeness validation. It does not compute features.
- `features.yml` is intentionally separate from ingest and supports explicit mode/date/symbol/timeframe inputs.
- SSI/Supabase credentials are provided through repository secrets.
- Do not add automatic signal or backtest execution to ingest workflows without an explicit architecture task.

## Validation

Review workflow YAML, run the corresponding local command, and rely on `tests.yml` for offline test coverage before merging.
