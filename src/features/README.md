# Feature Package

This package computes features from clean database tables only. It does not call SSI APIs, ingest source data, generate signals, run backtests, or send alerts.

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

Production persists only:

- `1d` from `stock_daily`;
- `15m` and `60m` aggregated in memory from clean `stock_intraday` 1m candles.

Feature rows for `1m` and `5m` are rejected. Canonical 1m source candles remain stored in `stock_intraday`.

## File responsibilities

| File | Responsibility |
| --- | --- |
| `daily.py` | Read `stock_daily`, compute `1d`, write `features`. |
| `intraday.py` | Read clean 1m, aggregate closed 15m/60m buckets, compute intraday features. |
| `backfill.py` | Inclusive date-range feature recomputation with historical warm-up; write only the requested range. |
| `common.py` | Shared formulas and dataframe helpers. |
| `runtime.py` | DB reads, serialization, upsert, date helpers, and summaries. |
| `runner.py` | Compatibility router and lower-level compatibility functions. |
| `policy.py` | Public production timeframe defaults and persistence validation. |

Production imports should come from `src.features`.

## CLI scopes

The source-specific commands support exactly one scope per run.

### One target date

```bash
python main.py features-daily --date 10/07/2026 --symbols SSI HPG
python main.py features-intraday --date 10/07/2026 --symbols SSI HPG --timeframes 15m 60m
```

For a current-day closed-bucket cutoff:

```bash
python main.py features-intraday --date 10/07/2026 --as-of 14:30 --symbols SSI
```

### Inclusive date range

```bash
python main.py features-daily \
  --from 01/07/2026 \
  --to 29/07/2026 \
  --symbols SSI HPG
```

```bash
python main.py features-intraday \
  --from 01/07/2026 \
  --to 29/07/2026 \
  --symbols SSI HPG \
  --timeframes 15m 60m
```

Range mode reads source history through the end date, computes indicators once with earlier observations available for warm-up, then upserts only feature rows inside the inclusive requested range.

### Full history

```bash
python main.py features-daily --mode full --symbols SSI HPG
python main.py features-intraday --mode full --symbols SSI HPG --timeframes 15m 60m
```

## Scope validation

The CLI returns exit code `2` when:

- only one of `--from` or `--to` is supplied;
- `--date` is combined with `--from/--to`;
- `--mode full` is combined with `--date` or `--from/--to`;
- `--as-of` is used with range mode;
- incremental mode has neither `--date` nor `--from/--to`;
- the date range is reversed or ends in the future.

## Correctness and safety

- Daily features are never calculated from intraday data.
- 15m/60m bars are aggregated from clean 1m in memory and are not written back to `stock_intraday`.
- Intraday writes only closed buckets.
- EMA/RSI/MACD have prior history available for warm-up.
- Missing inputs remain `NULL`; they are not forced to zero or `False`.
- `stock_intraday.value` remains an estimate based on `round(close * volume)`.
- Feature execution remains separate from ingest, signals, and backtests.

## Database impact

Migration: none.

Range and full runs write only to `features`. Source tables are read-only. No source-data backfill is triggered automatically.