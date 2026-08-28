# Trading T+

Python data foundation for analyzing Vietnamese stocks over an approximate T+3
to T+5 trading-session horizon.

The repository has closed **Phase 0: data foundation and validation** as
`COMPLETE_WITH_NOTES`. Data
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
- Phase 1 historical analog contract: [docs/phase1/HISTORICAL_ANALOG_SPEC.md](docs/phase1/HISTORICAL_ANALOG_SPEC.md)
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
stock_features
    ↓
Phase 1 historical analog research (EOD V1 core implemented)
```

Non-negotiable rules:

- Daily and intraday pipelines remain separate.
- Raw and clean data remain separate.
- Ingest does not automatically compute features. Feature execution does not automatically run signal or backtest logic.
- `stock_daily` is the canonical source for `1d` features.
- `stock_intraday` persists only canonical `timeframe='1m'` source candles.
- Persisted feature timeframes are only `1d`, `15m`, and `60m`.
- `15m` and `60m` are aggregated from clean 1m candles in memory.
- `1m` and `5m` feature rows are not persisted in `stock_features`.
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
python main.py stock-eod [DD/MM/YYYY] --symbols SSI HPG
python main.py backfill-daily --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py backfill-intraday --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py backfill --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py refill --symbol SSI --from DD/MM/YYYY --to DD/MM/YYYY
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
- **Incremental** reads the latest `stock_features.time` watermark independently for
  each symbol/timeframe. Daily uses five years of `stock_daily` warm-up;
  intraday uses the latest 250 observed trading sessions of clean 1m candles.
  Calculation uses the complete loaded window, but writes only rows after the
  watermark through the target date (or only the target date when no watermark
  exists).
- **Replace / rebuild-clean** is reserved for an atomic, precisely scoped
  rebuild. The CLI requires exactly one symbol, one timeframe, and both range
  bounds, accepts only `1d`/`15m`/`60m`, and rejects `start > end`. The application computes and validates before one atomic RPC; deploy the new migration before use.

Range commands remain explicit backfills. No feature mode is invoked by ingest.
`refill` is the explicit exception: a single-symbol maintenance orchestrator that
runs combined source backfill and completeness first, then upserts only `1d`,
`15m`, and `60m` features. It never syncs master data or runs downstream analysis.

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

No schema migration is required. Existing `stock_features` rows with timeframe `1m`
or `5m` are not deleted automatically. Any cleanup must be a separate,
explicitly scoped database operation. Source data does not require backfill.

## Project status

Phase 0 is closed as `COMPLETE_WITH_NOTES`. Phase 1 now has an accepted design:
at each checkpoint, a symbol is compared only with its own historical states at
the same checkpoint, then configured outcomes are summarized (V1 H+1/H+3/H+5;
EOD V2 adds H+10). Cross-symbol
sample pooling is forbidden; inadequate evidence returns `insufficient_sample`.

The superseded fixed-rule strategy/signal/backtest runtime, CLI, tests, and
schema snapshot have been removed. Historical Analog EOD V1 now provides the
implemented Phase 1 backend foundation; its null distance threshold and draft
profile still block approval and production queries. See the
[Phase 1 specification](docs/phase1/HISTORICAL_ANALOG_SPEC.md).

### Feature rebuild contract
Feature daily reads paginate all matching `stock_daily` rows. `full` remains non-destructive upsert; `incremental` uses per-stream watermarks with five years of daily or 250 observed intraday-session warm-up; `replace` (`rebuild-clean`) computes and validates one exact symbol/timeframe/inclusive Vietnam-date range before one atomic RPC. Empty incremental output is a successful no-op. Deploy `migrations/20260802_atomic_replace_features.sql` before using replace.

Pagination continues after a short server-capped page, advances by the actual
returned row count, and terminates on an empty page (or an exact requested
limit). The complete oldest selected intraday session is retained even when it
crosses a page boundary. Deterministic long-history tests compare every
persisted column for `1d`, `15m`, and `60m`; see the
[Phase 0 validation report](docs/phase0/PHASE0_VALIDATION_REPORT.md). Phase 0 is
**COMPLETE_WITH_NOTES**: the owner verified the manually applied production
schema and scoped live lineage/reconciliation samples. Remaining calendar and
evidence-retention risks are recorded in the report; the Historical Analog EOD V1 core is implemented, with final validation and approval still pending.

### Index daily source pipeline

Use `index-daily`, `index-backfill`, and the read-only `index-check` commands for SSI DailyIndex. The layered contract is `index_master` scope → `index_raw_daily` payload evidence → validated `index_daily`; The separate index-eod flow handles this without calculating downstream features or research results. See the [CLI usage guide](docs/CLI_USAGE.md).
The normalized `index_daily` identity and primary key is
`(index_code, trading_date)`: one row per index and trading date.

Index Daily Feature V1 is intentionally separate from ingestion and stock
features: it reads clean `index_daily` and writes the dedicated
`index_features_daily` table. Use `index-features-preview`,
`index-features-daily`, `index-features-backfill`, and the read-only
`index-features-check`; see the [index feature guide](src/index_features/README.md).

Before ingest, `index-preview` can inspect SSI directly without constructing a
database client or writing raw/clean rows. All index CLI dates accept `YYYY-MM-DD` or
`DD/MM/YYYY`; ranges are inclusive. Missing SSI values remain `null` in JSON
and `-` in the human-readable table. `--indexes` is required and accepts one
comma-separated value; preview does not resolve omitted scope from the database.

```bash
python main.py index-preview --date 2026-08-24 --indexes VNINDEX
python main.py index-preview --from 2026-08-01 --to 2026-08-24 --indexes VNINDEX,HNXINDEX
python main.py index-preview --date 2026-08-24 --indexes VNINDEX --raw
python main.py index-preview --date 2026-08-24 --indexes VNINDEX --json
```

The raw preview preserves the complete SSI item and includes a mapping summary;
the normalized JSON includes every clean `index_daily` field, retaining missing
values as `null`. The complete 23-field source-to-raw-to-clean audit, including
aliases and the intentionally raw-only `Time` field, is documented in
[SSI DailyIndex field mapping](docs/SSI_DAILY_INDEX_MAPPING.md).

`--raw` prints the SSI payload rows returned by the existing paginated client;
`--json` prints normalized records. The command never inserts, upserts, deletes,
calculates features, or runs signals/backtests. Preview first, verify the fields
and values, run `index-daily` or `index-backfill`, then run `index-check`.

### Stock table rename deployment

Deploy the application and `migrations/20260826_standardize_stock_table_names.sql` together in a maintenance window: pause scheduled and manual writers, apply the migration manually in Supabase, confirm its read-only verification queries and PostgREST schema reload, deploy this code, smoke-test reads/writes, and only then resume writers. The migration preserves rows and requires no backfill; do not deploy code before the database rename or resume old code afterward.

### 2026-08-27 domain-name correction deployment

The manually applied `20260826_standardize_stock_table_names.sql` migration had
an over-broad scope. `migrations/20260827_restore_domain_table_names.sql` restores
master data (`symbols`, `securities`), Phase 1 (`analog_*`), and streaming
(`stream_*`) names while retaining the six stock pipeline names. This is a
metadata-only correction; no backfill or feature/Analog rebuild is required.

Safe deployment order: (1) pause scheduled GitHub Actions and all database
writers; (2) run `sql/verify_restore_domain_table_names.sql` and retain its table
counts/catalog output; (3) manually apply the corrective migration in Supabase;
(4) rerun the read-only verification and compare counts; (5) deploy the corrected
code; (6) run read-only CLI/Supabase smoke checks; and (7) resume workflows only
when database and code agree. If migration verification fails, keep writers
paused: an in-transaction error rolls back atomically; after commit, use the
collision-checked reverse-rename guidance at the end of the migration together
with the matching old application release, then reload PostgREST. Do not create
compatibility views without a separate consumer and security review.

See the [Stock EOD pipeline contract](docs/STOCK_EOD_PIPELINE.md) for its active-only stock scope and explicit separation from `index-eod`.
