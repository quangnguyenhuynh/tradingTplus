# Trading T+

Python data foundation for analyzing Vietnamese stocks over an approximate T+3
to T+5 trading-session horizon.

The repository is in **Phase 0: data foundation and validation**. Data
correctness, SSI contract verification, reproducible pipelines, and completeness
checks take priority over signals, backtests, profitability, or AI optimization.

## Documentation

- Tiếng Việt: [README.vi.md](README.vi.md)
- Project overview: [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)
- Current state: [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md)
- Architecture decisions: [docs/ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md)
- Data conventions: [docs/DATA_CONVENTIONS.md](docs/DATA_CONVENTIONS.md)
- CLI reference: [docs/CLI_USAGE.md](docs/CLI_USAGE.md)
- Feature package: [src/features/README.md](src/features/README.md)
- Database contract: [schema.sql](schema.sql) and [migrations/](migrations/README.md)

Code, schema, migrations, and tests are the source of truth when older documents
conflict with executable behavior.

## Architecture contracts

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
future downstream research (not implemented)
```

Non-negotiable rules:

- Daily and intraday pipelines remain separate.
- Raw and clean data remain separate.
- Ingest does not automatically compute features. Feature execution does not automatically run signal or backtest logic.
- `stock_daily` is the canonical source for `1d` features.
- `stock_intraday` persists only canonical `timeframe='1m'` source candles.
- Persisted feature timeframes are only `1d`, `15m`, and `60m`.
- `15m` and `60m` are aggregated from clean 1m candles in memory.
- `1m` and `5m` feature rows are not persisted in `features`.
- All feature output stays in one table keyed by `(symbol, timeframe, time)`.
- Missing or unsupported market data is not fabricated as zero-valued rows.

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

Never commit real credentials, tokens, or `.env` contents.

## Production CLI

Source ingest:

```bash
python main.py sync-master-data
python main.py init
python main.py daily [DD/MM/YYYY] --symbols SSI HPG
python main.py intraday-ingest [DD/MM/YYYY] --symbols SSI HPG
python main.py eod [DD/MM/YYYY] --symbols SSI HPG
python main.py backfill-daily --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py backfill-intraday --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py backfill --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
```

Feature execution remains explicit and separate:

```bash
python main.py features-daily --date DD/MM/YYYY --symbols SSI HPG
python main.py features-daily --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py features-daily --mode full --symbols SSI HPG
python main.py features-intraday --date DD/MM/YYYY --symbols SSI HPG --timeframes 15m 60m
python main.py features-intraday --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG --timeframes 15m 60m
python main.py features-intraday --mode full --symbols SSI HPG --timeframes 15m 60m
python main.py features --mode incremental --date DD/MM/YYYY --symbols SSI HPG --timeframes 15m 60m 1d
```

Feature execution has three explicit semantics:

- **Full** loads the complete selected source history, recomputes it, and
  upserts every result. It never deletes existing feature rows first.
- **Incremental** reads the latest `features.time` watermark independently for
  each symbol/timeframe. Daily uses five years of `stock_daily` warm-up;
  intraday uses the latest 250 observed trading sessions of clean 1m candles.
  Calculation uses the complete loaded window, but writes only rows after the
  watermark through the target date (or only the target date when no watermark
  exists).
- **Replace / rebuild-clean** is reserved for an atomic, precisely scoped
  rebuild. The CLI requires exactly one symbol, one timeframe, and both range
  bounds, accepts only `1d`/`15m`/`60m`, and rejects `start > end`. This
  repository has no verified atomic replace RPC yet, so a complete
  request fails safely without deleting or writing anything. Use non-destructive
  `full` until that database contract is implemented.

Range commands remain explicit backfills. No feature mode is invoked by ingest.

The legacy alias persists only 15m/60m features:

```bash
python main.py intraday --symbols SSI HPG --timeframes 15m 60m
```

The following are intentionally rejected by production feature runners:

```bash
python main.py features-intraday --timeframes 1m
python main.py features-intraday --timeframes 5m
python main.py features --timeframes 1m 5m 1d
```

Use `intraday-ingest` to store canonical 1m source candles. See the
[feature guide](src/features/README.md) for the difference between 1m source
candles and persisted feature rows.

## Tests

```bash
python -m compileall main.py src scripts
python main.py --help
python -m pytest -q
```

SSI and Supabase integration checks require credentials and should remain
read-only unless an explicit scoped write test is intended.

## Database impact of feature timeframe policy

No schema migration is required. Existing `features` rows with timeframe `1m`
or `5m` are not deleted automatically. Any cleanup must be a separate,
explicitly scoped database operation. Source data does not require backfill.

## Project status

The legacy signal and backtest MVP code has been removed. These layers will be
redesigned in a later phase after data and feature contracts are verified; no
executable signal or backtest path is currently provided.
