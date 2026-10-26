# TradingTPlus — SSI v3

[Tiếng Việt](README.vi.md) · [CLI quick guide](docs/CLI_USAGE.md) · [Full reference](docs/CLI_REFERENCE.md)

TradingTPlus researches Vietnamese stocks over T+3–T+5 sessions. **Ingestion, features and research are independent steps.** Features do not automatically start signals, alerts, backtests, or NAV allocation.

## Getting started

Use Python 3.11 and run all commands from the **repository root**. Set up SSI and Supabase credentials locally in `.env` for ingestion; features require DB credentials. Never commit secrets.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
python main.py --help
```

**Do not run WRITE examples merely to test documentation.** Dates and symbols below are historical examples.

## Common CLI commands

| Task | Command | Effect |
| --- | --- | --- |
| Preview raw SSI | `python scripts/inspectors/ssi_rest/inspect.py run stock-daily --symbol SSI --date 19/10/2026 --show-mapping` | READ |
| Ingest stock EOD | `python main.py stock-eod 19/10/2026 --symbols SSI` | WRITE |
| Stock backfill | `python main.py stock-daily-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI` | WRITE |
| Preview index | `python main.py index-preview --date 19/10/2026 --indexes VNINDEX --json` | READ |
| Ingest index | `python main.py index-daily 19/10/2026 --indexes VNINDEX` | WRITE |
| Preview intraday | `python main.py stock-intraday 20/10/2026 --symbols SSI` | DRY-RUN |
| Compute daily features | `python main.py features-daily --date 19/10/2026 --symbols SSI` | WRITE |
| Foreign ranking | `python main.py foreign-rank --date 19/10/2026 --ranking accumulation --window 5 --top 20` | READ |
| Stock screener | `python main.py stock-screener --date 19/10/2026 --symbols SSI --version v2` | READ by default |

See the [task-based CLI guide](docs/CLI_USAGE.md) for `--write` intraday, backfill, index/foreign features and status meanings. Review DRY-RUN/preflight before any intraday write.

## Data flow

`SSI v3 → raw → clean → (data quality) → independent features → independent research`.

1d stock features read `stock_daily`; intraday stores 1m separately and derives 15m/60m features from clean 1m. Validate raw, clean and features independently.

## Important safeguards

- Master records must exist: `init` and `sync-master-data` route to guarded sync, but all SSI v3 master datasets remain BLOCKED pending verified source fixtures. Automated `intraday-ingest`, combined `backfill`, `refill`, and `streaming-ingest` remain disabled.
- Intraday manual pilot and guarded range backfill default to DRY-RUN; only `--write` persists. Completeness is unverified; never assume 226 bars per day.
- Exit 0/OK alone does not prove completeness; inspect PARTIAL/BLOCKED/EMPTY.
- `replace`/`rebuild-clean` may replace scoped feature data; read the reference and check DB before use.

## Detailed documentation

[CLI guide](docs/CLI_USAGE.md) · [Full CLI reference](docs/CLI_REFERENCE.md) · [Backfill runbook](docs/backfill/README.md) · [Intraday runbook](docs/STOCK_INTRADAY_PIPELINE.md) · [Scripts](scripts/README.md) · [Architecture](src/README.md) · [Data conventions](docs/DATA_CONVENTIONS.md) · [Current state](docs/CURRENT_STATE.md).

## Offline checks

```bash
python main.py --help
python -m compileall main.py src scripts tests
python -m pytest -q tests/cli tests/inspectors
```

## Master sync — updated 26 October 2026

`sync-master-data` and alias `init` now use guarded orchestration, default DRY_RUN. All four SSI v3 datasets are BLOCKED; production master bootstrapping remains unavailable. No ready provider means no API/DB access. --write requires one explicit --dataset and a READY provider. Operator statuses are preserved; new stocks/indexes inactive. No migration or price backfill. [Runbook and PARTIAL report](src/ingest/master/README.md).
