# Feature Package

This package computes **features from clean database tables only**. It does not
call SSI APIs, ingest raw/clean data, create signals, run backtests, or send
alerts.

All feature flows write to one table:

```text
stock_daily / stock_intraday
        |
        v
src/features
        |
        v
features(symbol, timeframe, time, ...)
```

## 1. Daily vs Intraday

| Flow | Reads from | Writes timeframe | Purpose |
| --- | --- | --- | --- |
| Daily feature | `stock_daily` | `1d` | Main T+3/T+5 context: trend, momentum, and daily liquidity. |
| Intraday feature | `stock_intraday` 1m | `1m`, `5m`, `15m`, `60m` | Intraday confirmation and entry timing. |

Daily and intraday now have separate execution paths:

- `features-daily` reads only `stock_daily`;
- `features-intraday` reads canonical 1m `stock_intraday` and reads
  `stock_daily` only for official open / previous close context;
- 5m/15m/60m bars are aggregated from 1m in memory and are never written back to
  `stock_intraday`;
- both flows write to the same `features` table and differ by `timeframe`.

## 2. File Responsibilities

| File | Plain responsibility |
| --- | --- |
| `daily.py` | Daily feature flow: read `stock_daily`, compute `1d`, write `features`. |
| `intraday.py` | Intraday feature flow: read 1m, aggregate 5m/15m/60m, keep closed buckets, write `features`. |
| `common.py` | Shared formulas: EMA, RSI, MACD, returns, breakout, candle fields, nullable flags. |
| `runtime.py` | Shared runtime helpers: date/timeframe normalization, paginated DB reads, upsert, summaries. |
| `runner.py` | Compatibility router for the old mixed `features` command. New code should call source-specific modules. |

The old `src/engine/feature_engine.py` and
`src/engine/feature_calculator.py` shims were removed. New imports should use:

```python
from src.features.daily import run_daily_features_with_summary
from src.features.intraday import run_intraday_features_with_summary
```

## 3. Run One Target Date

Daily feature for one date:

```bash
python main.py features-daily --mode incremental --date 10/07/2026 --symbols SSI HPG
```

This:

- reads `stock_daily` up to the target date;
- recomputes indicators with prior history for warm-up;
- writes only `timeframe = 1d` rows whose `time` falls on the target date.

Intraday feature for one date:

```bash
python main.py features-intraday --mode incremental --date 10/07/2026 --symbols SSI HPG --timeframes 1m 5m 15m 60m
```

This:

- reads all available prior 1m history up to the target date so incremental
  output matches full mode;
- aggregates 5m/15m/60m in memory;
- writes only closed buckets;
- upserts only output rows from the target date.

For a current-day alert-style run:

```bash
python main.py features-intraday --mode incremental --date 10/07/2026 --as-of 14:30 --symbols SSI
```

`--as-of 14:30` means only buckets closed by 14:30 Vietnam time are eligible to
write.

## 4. Full / Backfill Feature Runs

There is currently no feature range command such as:

```bash
python main.py features-intraday --from-date ... --to-date ...
```

Historical feature recomputation is done in one of two ways.

### Option A - Full Mode

```bash
python main.py features-daily --mode full --symbols SSI HPG
python main.py features-intraday --mode full --symbols SSI HPG --timeframes 1m 5m 15m 60m
```

Full mode reads all source rows currently available in the database and rewrites
the corresponding feature rows. This is the canonical backfill path after a
formula/schema change has been approved.

Notes:

- do not pass `--date` in full mode;
- scope is based on what exists in `stock_daily` / `stock_intraday`;
- this is a real database write into `features`;
- test with a small `--symbols` list before expanding the scope.

### Option B - Incremental One Date at a Time

```bash
python main.py features-daily --mode incremental --date 10/07/2026 --symbols SSI
python main.py features-intraday --mode incremental --date 10/07/2026 --symbols SSI --timeframes 1m 5m 15m 60m
```

Use this for a targeted one-day repair. If multiple dates need incremental
repair, loop over dates outside this CLI, for example in shell or GitHub
Actions. The repo does not yet provide a built-in feature range CLI.

## 5. Compatibility Commands

The old mixed command still works:

```bash
python main.py features --mode incremental --date 10/07/2026 --symbols SSI --timeframes 1d 1m 5m 15m 60m
```

It is a compatibility router. Prefer source-specific commands for operations:

- `features-daily` for `1d`;
- `features-intraday` for `1m/5m/15m/60m`.

The legacy `intraday` command is also a feature alias, not ingest:

```bash
python main.py intraday --symbols SSI --timeframes 1m 5m 15m
```

Use this command to ingest SSI intraday candles instead:

```bash
python main.py intraday-ingest 10/07/2026 --symbols SSI
```

## 6. Correctness Rules

- Daily features are not calculated from intraday data.
- Intraday 5m/15m/60m are always aggregated from clean 1m rows.
- Intraday writes only closed candles/buckets.
- Intraday EMA/RSI/MACD continue across observed dates; they do not reset daily.
- Intraday `high_20_bars` / `low_20_bars` look at previous bars to avoid
  look-ahead.
- Intraday VWAP resets daily.
- Intraday `volume_ma20` / `value_ma20` compare with the same local bucket from
  the previous 20 observed dates, not the previous 20 bars from the same day.
- Boolean flags remain `NULL` when inputs are missing; missing data is not forced
  to `False`.
- Intraday `return_from_open` uses official `stock_daily.open_price`; missing
  context remains `NULL`.

## 7. Intraday Value and VWAP

`stock_intraday.value` is currently an estimate:

```text
value ~= round(close * volume)
```

Therefore `vwap_intraday` is an approximate candle-close/volume VWAP, not exact
exchange turnover VWAP. It can help describe intraday position, but should not be
explained as precise SSI turnover data.

## 8. Migration and Backfill After Issue #99

Migration `20260729_drop_legacy_feature_columns.sql` removes unused legacy
feature columns. Apply it manually after review; deployment does not run it
automatically.

After deploying the migration/correctness change, rerun features so the
`features` table is consistent with the current formulas:

```bash
python main.py features-daily --mode full --symbols SSI HPG
python main.py features-intraday --mode full --symbols SSI HPG --timeframes 1m 5m 15m 60m
```

For production, start with a few symbols, inspect summaries/output, then expand
the scope.

## 9. Current Limits

- No integrated exchange holiday calendar; holidays/halts are inferred from
  available data.
- No built-in feature backfill range CLI with `--from-date` / `--to-date`.
- Full mode can be heavy because it reads all available history for indicator
  parity.
- Feature commands are database writes, not read-only smoke tests.
- Signal/backtest does not run automatically after features.
