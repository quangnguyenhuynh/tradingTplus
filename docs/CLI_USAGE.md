# TradingTPlus CLI usage

Production command reference for Phase 0 data foundation and validation.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Command completed with `OK` or `PARTIAL`. Review the JSON summary. |
| `1` | Command returned `FAILED` or raised an unhandled runtime error. |
| `2` | Invalid CLI arguments, date, symbol scope, or feature timeframe. |

## Operating order

```text
sync-master-data
→ daily / intraday-ingest / eod / backfill
→ validation and completeness
→ feature commands run explicitly and separately
```

Source ingest never runs features, signals, or backtests automatically.

## Source-data commands

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

### `daily`

Reads SSI `DailyStockPrice`; writes `raw_daily` and canonical `stock_daily`.
It does not ingest intraday data or calculate features.

### `intraday-ingest`

Reads SSI `IntradayOhlc` resolution `1`; writes `raw_intraday` and canonical
`stock_intraday` with `timeframe='1m'`.

The persisted 1m rows are source candles. They are not feature rows.

### `eod`

Runs daily ingest, intraday ingest, then completeness validation. It does not
run the feature pipeline.

### Backfill commands

Dates use `DD/MM/YYYY`, both endpoints are inclusive, weekends are skipped, and
weekday empty API responses remain observable. No downstream feature backfill
runs automatically.

## Feature persistence policy

The `features` table persists only:

```text
1d
15m
60m
```

Policy by source:

| Persisted timeframe | Source | Product role |
| --- | --- | --- |
| `1d` | `stock_daily` | Main T+3/T+5 trend, momentum, liquidity, and price context. |
| `15m` | aggregate from clean `stock_intraday` 1m | Entry timing and intraday confirmation. |
| `60m` | aggregate from clean `stock_intraday` 1m | Broader intraday confirmation. |

Feature persistence for `1m` and `5m` is rejected. Clean 1m source candles are
still required and remain stored in `stock_intraday`.

## `features-daily`

One target date:

```bash
python main.py features-daily \
  --mode incremental \
  --date 10/07/2026 \
  --symbols SSI HPG
```

Full recomputation:

```bash
python main.py features-daily --mode full --symbols SSI HPG
```

Behavior:

- reads only `stock_daily`;
- computes only `timeframe='1d'`;
- writes only to `features`;
- does not ingest data, create signals, or run backtests.

## `features-intraday`

One target date:

```bash
python main.py features-intraday \
  --mode incremental \
  --date 10/07/2026 \
  --symbols SSI HPG \
  --timeframes 15m 60m
```

Current-day closed-bucket cutoff:

```bash
python main.py features-intraday \
  --mode incremental \
  --date 10/07/2026 \
  --as-of 14:30 \
  --symbols SSI \
  --timeframes 15m 60m
```

Full recomputation:

```bash
python main.py features-intraday \
  --mode full \
  --symbols SSI HPG \
  --timeframes 15m 60m
```

Behavior:

- reads canonical clean 1m `stock_intraday` rows;
- reads `stock_daily` only for official open and previous-close context;
- aggregates 15m/60m in memory;
- writes only closed buckets to `features`;
- does not write aggregate candles back to `stock_intraday`.

## `features` compatibility router

```bash
python main.py features \
  --mode incremental \
  --date 10/07/2026 \
  --symbols SSI HPG \
  --timeframes 15m 60m 1d
```

Default persisted timeframes are `15m 60m 1d`. Prefer `features-daily` and
`features-intraday` for operational clarity.

## `intraday` legacy alias

```bash
python main.py intraday --symbols SSI HPG --timeframes 15m 60m
```

This is a feature alias, not SSI candle ingest. It persists only 15m/60m
features. Use `intraday-ingest` to fetch and store 1m source candles.

## Invalid feature commands

These return exit code `2`:

```bash
python main.py features-intraday --timeframes 1m
python main.py features-intraday --timeframes 5m
python main.py features --timeframes 1m 5m 1d
python main.py intraday --timeframes 1m
```

## Streaming ingest

```bash
python main.py streaming-ingest \
  --symbols SSI \
  --channels quote \
  --timeout 60 \
  --max-messages-per-channel 1
```

The command is bounded and read-only unless `--write` is supplied.

## Symbol scope

Commands accepting `--symbols` normalize values by stripping whitespace,
uppercasing, and deduplicating in first-seen order. Source-ingest commands use
all master symbols when the option is omitted. Explicit blank scopes are
invalid.

## Database impact of the timeframe policy

No schema migration is required. Existing `features` rows with timeframe `1m`
or `5m` are not deleted automatically. Cleanup must be a separate, explicitly
scoped database operation. No source-data backfill is required.

## Validation commands

```bash
python -m compileall main.py src scripts
python main.py --help
python -m pytest -q
```

SSI and Supabase integration checks require credentials and should remain
read-only unless an explicit scoped write test is intended.
