# Feature Package

This package computes features from clean database tables only. It does not call
SSI APIs, ingest source data, generate signals, run backtests, or send alerts.

All persisted feature rows use one table:

```text
stock_daily / stock_intraday
        |
        v
src/features
        |
        v
features(symbol, timeframe, time, ...)
```

## Persisted timeframe policy

Production persistence is intentionally limited to:

- `1d`: main T+3/T+5 context from `stock_daily`;
- `15m`: entry timing and intraday confirmation;
- `60m`: broader intraday confirmation.

`stock_intraday` still stores canonical `1m` candles. Those 1m candles are the
source used to aggregate 15m and 60m bars in memory. The production feature
runners reject persistence for `1m` and `5m`.

This distinction is important:

```text
1m source candles: required and persisted in stock_intraday
1m/5m feature rows: not persisted in features
```

Lower-level aggregation/calculator functions may still support research and
offline tests, but public runners under `src.features` enforce the production
persistence policy.

## Daily and intraday flows

| Flow | Reads from | Writes timeframe | Purpose |
| --- | --- | --- | --- |
| Daily feature | `stock_daily` | `1d` | Trend, momentum, daily liquidity, and price structure for T+3/T+5. |
| Intraday feature | `stock_intraday` 1m plus daily context | `15m`, `60m` | Intraday confirmation and entry timing. |

Rules:

- daily features are never calculated from intraday data;
- 15m/60m bars are aggregated from clean 1m candles in memory;
- aggregated bars are not written back to `stock_intraday`;
- both flows write to the same `features` table;
- feature execution remains separate from ingest, signals, and backtests.

## File responsibilities

| File | Responsibility |
| --- | --- |
| `daily.py` | Read `stock_daily`, compute `1d`, write `features`. |
| `intraday.py` | Read clean 1m, aggregate bars, keep closed buckets, compute intraday features. |
| `common.py` | Shared formulas and dataframe helpers. |
| `runtime.py` | Shared DB reads, serialization, upsert, date helpers, and summaries. |
| `runner.py` | Historical compatibility router and lower-level compatibility functions. |
| `policy.py` | Public production timeframe defaults and rejection of 1m/5m feature writes. |

Public production imports should come from `src.features`, not directly from
`src.features.runner` or `src.features.intraday`.

## CLI

Daily feature for one date:

```bash
python main.py features-daily --mode incremental --date 10/07/2026 --symbols SSI HPG
```

Inclusive range backfill (indicators use prior history for warm-up, but only range rows are written):

```bash
python main.py features-daily --from 01/07/2026 --to 29/07/2026 --symbols SSI HPG
python main.py features-intraday --from 01/07/2026 --to 29/07/2026 --symbols SSI HPG --timeframes 15m 60m
```

`--from-date` and `--to-date` remain aliases. `--as-of` is only valid with a single `--date`, not a range. Source tables are read-only; range execution upserts only `features` and does not require source-data backfill.

Intraday feature for one date:

```bash
python main.py features-intraday --mode incremental --date 10/07/2026 --symbols SSI HPG --timeframes 15m 60m
```

Current-day closed-bucket cutoff:

```bash
python main.py features-intraday --mode incremental --date 10/07/2026 --as-of 14:30 --symbols SSI
```

Full recomputation:

```bash
python main.py features-daily --mode full --symbols SSI HPG
python main.py features-intraday --mode full --symbols SSI HPG --timeframes 15m 60m
```

Full recalculates and upserts all selected history; it never deletes first.
Incremental resolves a watermark for each symbol/timeframe, calculates with
five years of daily warm-up or 250 observed intraday sessions, and writes only
the target rows. If no watermark exists, it writes only the requested target
date. `1m` and `5m` remain calculator/source granularities and cannot be
persisted as feature timeframes.

`replace` / `rebuild-clean` requires exactly one symbol, one persisted
timeframe, and `--from`/`--to` with start not later than end. Because no verified
atomic replace backend exists, the command currently fails before every write
or delete; it must not be treated as an operational cleanup command.

Compatibility router:

```bash
python main.py features --mode incremental --date 10/07/2026 --symbols SSI --timeframes 15m 60m 1d
```

Legacy alias:

```bash
python main.py intraday --symbols SSI --timeframes 15m 60m
```

The following production commands are invalid and return exit code `2`:

```bash
python main.py features-intraday --timeframes 1m
python main.py features-intraday --timeframes 5m
python main.py features --timeframes 1m 5m 1d
```

To ingest canonical 1m source candles, use:

```bash
python main.py intraday-ingest 10/07/2026 --symbols SSI
```

## Correctness notes

- Intraday writes only closed candles/buckets.
- Intraday EMA/RSI/MACD continue across observed dates.
- Intraday VWAP resets daily.
- `volume_ma20`/`value_ma20` use the same local bucket from prior observed dates.
- Missing inputs remain `NULL`; they are not forced to zero or `False`.
- Intraday `return_from_open` uses official `stock_daily.open_price` context.
- `stock_intraday.value` remains an estimate based on `round(close * volume)`.

## Database impact

No schema migration is required for this policy change. Existing `features`
rows with timeframe `1m` or `5m` are not deleted automatically. Removing them
must be a separate, explicitly scoped database operation after review.

No source-data backfill is required. Recompute only `1d`, `15m`, and `60m`
features when a formula change requires it.
