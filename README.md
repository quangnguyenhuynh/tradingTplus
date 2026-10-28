# TradingTPlus — SSI v3

## Canonical EOD CLI — 28 October 2026

| Command | Existing behavior retained |
| --- | --- |
| `stock-eod` | Stock ingest + existing daily completeness; active-symbol filtering |
| `stock-eod-backfill` | Inclusive stock daily backfill; no added completeness |
| `index-eod` | Existing index daily raw/clean ingest |
| `index-eod-backfill` | Existing inclusive index daily backfill |

Only these four top-level names are supported for stock/index EOD ingest/backfill.
Removed (no aliases/redirects): `daily`, `stock-daily`, `stock-daily-backfill`,
`backfill-daily`, `index-daily`, `index-daily-backfill`, `index-backfill`.
Old direct daily had different date/scope/completeness semantics and is retired;
stock-eod retains run_stock_eod_pipeline rather than adopting daily_run behavior.
Stock/index EOD defaults resolve the latest weekday on/before today in Vietnam;
original date validation, scope rules, summaries and exit codes remain unchanged.
Backfill date aliases --from/--from-date and --to/--to-date remain available.
PARTIAL can still exit 0 under existing _status_to_exit; no exit-policy changes.
Internal daily_run/run_daily_ingest/run_index_daily_ingest/backfill imports,
stock_daily/index_daily dataset IDs and JSON flows (including index-daily,
backfill-daily/index-backfill) remain unchanged. Inspector `stock-daily` remains.
Stock/index pipelines stay separate; no automatic feature/signal/backtest.
No migration/schema/data changes or required backfill. Do not execute WRITE
examples to verify naming. Historical naming/alias reports below are superseded.

```bash
python main.py stock-eod --help
python main.py stock-eod-backfill --help
python main.py index-eod --help
python main.py index-eod-backfill --help
```


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
| Stock backfill | `python main.py stock-eod-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI` | WRITE |
| Preview index | `python main.py index-preview --date 19/10/2026 --indexes VNINDEX --json` | READ |
| Ingest index | `python main.py index-eod 19/10/2026 --indexes VNINDEX` | WRITE |
| Preview intraday | `python main.py stock-intraday 20/10/2026 --symbols SSI` | DRY-RUN |
| Compute daily features | `python main.py features-daily --date 19/10/2026 --symbols SSI` | WRITE |
| Foreign ranking | `python main.py foreign-rank --date 19/10/2026 --ranking accumulation --window 5 --top 20` | READ |
| Stock screener | `python main.py stock-screener --date 19/10/2026 --symbols SSI --version v2` | READ by default |

See the [task-based CLI guide](docs/CLI_USAGE.md) for `--write` intraday, backfill, index/foreign features and status meanings. Review DRY-RUN/preflight before any intraday write.

## Data flow

`SSI v3 → raw → clean → (data quality) → independent features → independent research`.

1d stock features read `stock_daily`; intraday stores 1m separately and derives 15m/60m features from clean 1m. Validate raw, clean and features independently.

## Important safeguards

- Master records must exist: `init` and `sync-master-data` route to guarded sync, but symbols/securities can be synchronized with guarded three-board validation; index datasets remain BLOCKED. Automated `intraday-ingest`, combined `backfill`, `refill`, and `streaming-ingest` remain disabled.
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

## Master sync — updated 27 October 2026

`sync-master-data` and alias `init` now use guarded orchestration, default DRY_RUN. SSI v3 symbols/securities now support guarded refresh across HOSE/HNX/UPCOM; index_master/index_components remain BLOCKED. READY is scoped to guarded non-destructive refresh; authoritative market completeness remains UNVERIFIED. --write requires one explicit --dataset and a READY provider. Operator statuses are preserved; new stocks/indexes inactive. No migration or price backfill. [Runbook and validation report](src/ingest/master/README.md).

## Unified master cutover — 27 October 2026

This supersedes earlier independent symbols/securities procedures: symbols is the sole physical write target; securities is a deprecated CLI alias with an explicit warning. all syncs symbols once. Apply Stage A expansion/merge BEFORE application deployment; Stage B retirement is separately owner-approved and aborts by default. Never apply production migrations through the agent. VN50 GROWTH exact index exclusion is counted; HNX-request DERIVATIVES/Future retains its actual domain and inactive defaults. Index capabilities remain BLOCKED. No price backfill. [Runbook](src/ingest/master/README.md).
