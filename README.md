# Trading T+

Python data foundation for analyzing Vietnamese stocks over an approximate T+3 to T+5 trading-session horizon.

The repository is currently in **Phase 0: data foundation and validation**. Data correctness, SSI contract verification, reproducible pipelines, and completeness checks take priority over signals, backtests, profitability, or AI optimization.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)
- Project overview: [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)
- Current repository state: [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md)
- Architecture decisions: [docs/ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md)
- Data conventions: [docs/DATA_CONVENTIONS.md](docs/DATA_CONVENTIONS.md)
- CLI reference: [docs/CLI_USAGE.md](docs/CLI_USAGE.md)
- Production backfill: [docs/backfill/README.md](docs/backfill/README.md)
- Database notes: [docs_db_schema.md](docs_db_schema.md)

Repository code, schema, migrations, and tests are the source of truth when an older document conflicts with executable behavior.

## Architecture

```text
SSI sources
    ↓
raw data
    ↓
clean data
    ↓
validation and completeness
    ↓
features
    ↓
signals
    ↓
backtests
    ↓
alerts
```

Non-negotiable contracts:

- Daily and intraday pipelines remain separate.
- Raw and clean data remain separate.
- Ingest does not automatically compute features, signals, or backtests.
- `stock_daily` is the canonical source for `1d` features.
- `stock_intraday` persists only `timeframe='1m'`.
- `5m`, `15m`, and `60m` are aggregated from clean 1-minute candles in the feature pipeline.
- The accepted feature design is one `features` table keyed by `(symbol, timeframe, time)`.
- Missing or unsupported market data is not converted into fabricated zero-valued rows.

## Repository map

| Path | Responsibility |
| --- | --- |
| `main.py` | Production CLI entrypoint. |
| `src/ssi/` | SSI REST and streaming clients. |
| `src/pipeline/` | Master data, ingest, EOD, validation orchestration, backfill, and snapshots. |
| `src/database/` | Supabase access and persistence contracts. |
| `src/validation/` | Daily, intraday, and streaming validation. |
| `src/features/` | Source-isolated daily/intraday feature calculation and execution. |
| `src/engine/` | Downstream signal/backtest research and legacy quality utilities. |
| `scripts/` | Manual, smoke, debug, inspection, and maintenance tools. |
| `migrations/` | Versioned additive database changes. |
| `sql/` | Explicit operational SQL utilities. |
| `tests/` | Offline unit and contract tests. |
| `.github/workflows/` | CI and scheduled/manual workflows. |

Each tracked folder has English `README.md` and Vietnamese `README.vi.md` documentation.

Daily and intraday REST ingest each use dedicated `fetcher -> mapper -> validator integration -> persistence -> service` modules. `daily.py` and `intraday_ingest.py` are their independent batch orchestrators; `eod.py` only sequences both and runs completeness validation. The legacy `fetch_one_day.py` is a thin compatibility wrapper, not a second implementation. See [the pipeline module guide](src/pipeline/README.md) for the complete tree, ownership, retry behavior, and execution order.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Required credentials depend on the command:

```env
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SERVICE_KEY=
SSI_CONSUMER_ID=
SSI_CONSUMER_SECRET=
```

Never commit real credentials, access tokens, or `.env` contents.

## Production CLI

```bash
python main.py sync-master-data
python main.py init
python main.py daily [DD/MM/YYYY] --symbols SSI HPG
python main.py intraday-ingest [DD/MM/YYYY] --symbols SSI HPG
python main.py eod [DD/MM/YYYY] --symbols SSI HPG
python main.py backfill-daily --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py backfill-intraday --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py backfill --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py features --mode incremental --date DD/MM/YYYY --symbols SSI HPG --timeframes 1m 5m 15m 60m 1d
python main.py intraday --symbols SSI HPG
python main.py streaming-ingest --symbols SSI --channels quote --timeout 60 --max-messages-per-channel 1
```

Current behavior:

- `sync-master-data` / `init`: read SSI `Securities`, `SecuritiesDetails`, `IndexList`, and `IndexComponents`; write `symbols`, `securities`, `indexes`, and `index_components`.
- `daily`: read only SSI `DailyStockPrice`; write only `raw_daily` and `stock_daily`. It never calls or writes market-index data.
- `intraday-ingest`: read SSI `IntradayOhlc` resolution 1 plus optional DB `stock_daily` context; write `raw_intraday` and 1m `stock_intraday` only.
- `eod`: daily ingest → intraday ingest → completeness validation.
- `backfill-daily`: inclusive stock-daily-only range ingest (`DailyStockPrice` → `raw_daily` + `stock_daily`).
- `backfill-intraday`: inclusive intraday-only 1m ingest; uses existing daily context without creating it.
- `backfill`: complete daily branch → complete intraday branch → per-date completeness; no downstream features run automatically.
- `features`: explicit rerunnable feature pipeline.
- `intraday`: legacy intraday-feature alias; it does not fetch candles.
- `streaming-ingest`: bounded and read-only unless `--write` is supplied.

## Manual tools

Start with [scripts/README.md](scripts/README.md). The dedicated SSI inspectors are:

- [scripts/ssi_api_inspector/README.md](scripts/ssi_api_inspector/README.md)
- [scripts/ssi_streaming_inspector/README.md](scripts/ssi_streaming_inspector/README.md)

Debug and inspection tools should be read-only or dry-run by default. Any write or destructive operation must use explicit symbol/date scope.

## Tests

```bash
python -m compileall main.py src scripts
python main.py --help
python -m pytest -q
```

SSI and Supabase integration checks require credentials and should remain read-only unless an explicit scoped write test is intended.

## Database changes

Schema changes require a migration in [`migrations/`](migrations/README.md). Applying repository migrations to a real Supabase project is an explicit deployment step; repository presence does not prove that production has applied them.

## Project status

Signal and backtest code exists as research/MVP code but is not treated as validated product logic in Phase 0. Do not infer profitability, win rate, or production readiness from unverified data or historical documentation.

### Stock symbol scope for source ingest

`daily`, `intraday-ingest`, `eod`, `backfill-daily`, `backfill-intraday`, and `backfill` accept `--symbols` with one or more values. Omission uses all symbols from the existing master source. Explicit values are stripped, uppercased, deduplicated in first-seen order, and an empty explicit scope is invalid. Daily, EOD, and backfill never ingest market indexes; index master synchronization remains exclusive to `sync-master-data` / `init`. EOD passes one scope to daily, intraday, and stock-only completeness; backfill reuses it for every date. The legacy `intraday` command remains a feature alias, not candle ingest. No source ingest command automatically runs features, signals, or backtests.

> Feature execution update (issue #99): implementation is owned by `src/features/`. Use source-isolated `features-daily` and `features-intraday`; `features` and `intraday` are compatibility routes. Intraday persistence uses closed buckets, official daily open, continuous indicators/high-low, same-bucket prior-20-observed-date volume/value baselines, and nullable flags. See `src/features/README.md`.
