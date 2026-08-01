# Feature Pipeline

The feature pipeline turns **clean market data** into deterministic indicators
that later signal and backtest layers can use. Ingest and feature computation
are separate jobs:

- ingest collects and normalizes source data; it does not calculate features;
- a feature command reads clean tables and writes calculated rows;
- a feature command does not generate signals or run backtests.

This separation makes a feature run reproducible without fetching SSI data
again or changing the clean source rows.

## Data flow and timeframes

```text
stock_daily --------------------------------------> 1d features
                                                        |
stock_intraday (persisted 1m source candles)            v
        |                                         features table
        +-- aggregate in memory --> 15m features   (symbol, timeframe, time)
        +-- aggregate in memory --> 60m features
```

All results are upserted into the single `features` table. Its conflict key is
`(symbol, timeframe, time)`. Aggregated candles are not written back to
`stock_intraday`.

| Timeframe | Meaning | Source or persisted output? |
| --- | --- | --- |
| `1d` | Main T+3/T+5 trend, momentum, liquidity, and market context. | Persisted feature output, calculated only from `stock_daily`. |
| `60m` | Broader within-session confirmation and timing support. | Persisted feature output, aggregated from clean 1m candles. |
| `15m` | More detailed within-session timing. | Persisted feature output, aggregated from clean 1m candles. |
| `1m` | Canonical clean intraday source data. | Persisted in `stock_intraday`, **not** persisted as feature rows. |
| `5m` | Lower-level calculator granularity retained for research/tests. | **Not** persisted as production feature rows. |

The production runners accept only `1d`, `15m`, and `60m` feature output.
They never derive canonical `1d` features from intraday data and reject attempts
to persist `1m` or `5m` features.

## Execution modes

| Mode | When to use it | Data read | Data written | Does it delete data? |
| --- | --- | --- | --- | --- |
| `incremental` | Normal daily updates, or an explicit inclusive date-range backfill. | A target plus the history needed for correct indicators. | Only rows after the stream watermark through the target date; without a watermark, only the target date. A range command writes only its requested range. | No. It upserts. |
| `full` | Recalculate all available history for selected symbols/timeframes. | All available selected source history. | Every calculated row in that history. | No. It upserts and leaves rows outside the calculation result untouched. |
| `replace` / `rebuild-clean` | Eventually, replace one known-bad, exactly bounded stream. Do not use operationally yet. | An exact scope would be required. | Nothing with the current implementation. | No. It stops safely before any delete or write. |

An **upsert** inserts a missing key or updates an existing matching key. It is
not a blanket delete and rebuild.

### Incremental: watermark and warm-up

A **watermark** is the newest `features.time` already stored for one exact
`symbol + timeframe`. Each stream has its own watermark. The pipeline uses it
to determine where new output begins.

A **warm-up** is older clean data read only so rolling indicators such as EMA50,
RSI14, MACD, and 20-bar comparisons are correct. Reading warm-up data does not
mean rewriting it:

- `1d` reads up to five years of `stock_daily`, anchored at the watermark (or
  the target date when no watermark exists);
- `15m` and `60m` read up to the latest 250 observed Vietnam trading dates from
  `stock_intraday` 1m, ending at the target date;
- calculation uses the loaded window, but only the new or affected target range
  is upserted.

Example: suppose `SSI/1d` has a watermark of **30/07/2026** and clean data now
contains **31/07/2026**. An incremental run targeting 31/07/2026 reads older
`stock_daily` rows as warm-up, computes the indicators over that window, and
upserts only rows after 30/07/2026 through 31/07/2026. It does not rewrite the
five-year warm-up. If `SSI/1d` has no watermark, that same command writes only
31/07/2026.

### Full is non-destructive

Full loads all available history for the selected symbol(s), recalculates it,
and upserts all calculated rows. Full does **not** delete first and is not a
replace operation. If the database contains an old feature row outside the
new calculation result, full leaves that row in place.

The CLI does not allow `--mode full` together with `--date` or `--from/--to`.
Use the explicit range commands below to recompute a bounded date range without
deleting old rows.

### Replace / rebuild-clean is not operational

> **Current status:** replace/rebuild-clean cannot replace data yet. The CLI
> validates the mandatory scope and then stops safely because the database has
> no verified atomic replace operation. It deletes and writes nothing.

The required scope is exactly:

- one symbol;
- one persisted timeframe (`1d`, `15m`, or `60m`);
- start date/time (`--from`);
- end date/time (`--to`), with start not later than end.

Missing or broad scope is rejected. A valid scope also ends with an explicit
safe failure until atomic database support is implemented.

## Which mode should I use?

- **Daily update:** use `incremental` with `--date`.
- **Recompute a historical range without deleting rows:** use an explicit
  `--from/--to` range command.
- **Recompute all available selected history:** use `full`.
- **Remove and replace known-bad rows:** use `replace` only after an atomic
  replace backend is implemented and verified. It is unavailable now.
- Never use `full` expecting it to remove stale rows.

## Practical CLI guide

Dates use `DD/MM/YYYY`. Omitting `--symbols` means all symbols resolved by the
runner. The following commands match the current parser.

### Daily incremental

```bash
python main.py features-daily --mode incremental --date 31/07/2026 --symbols SSI HPG
```

Reads `stock_daily`, calculates `1d`, and upserts only rows after each symbol's
`1d` watermark through the target date. With no watermark, it writes only the
target date. It does not delete rows.

### Intraday 15m incremental

```bash
python main.py features-intraday --mode incremental --date 31/07/2026 --symbols SSI HPG --timeframes 15m
```

Reads clean `stock_intraday` 1m candles plus `stock_daily` context, aggregates
closed 15m buckets, and upserts the target region after each `15m` watermark.
It does not delete rows.

### Intraday 60m incremental

```bash
python main.py features-intraday --mode incremental --date 31/07/2026 --symbols SSI HPG --timeframes 60m
```

Reads the same clean sources, aggregates closed 60m buckets, and upserts the
target region after each `60m` watermark. It does not delete rows. For a live
day, `--as-of 14:30` may be supplied to set a Vietnam-time cutoff; only buckets
closed by that cutoff are eligible.

### Inclusive historical ranges

```bash
python main.py features-daily --from 01/07/2026 --to 31/07/2026 --symbols SSI
python main.py features-intraday --from 01/07/2026 --to 31/07/2026 --symbols SSI --timeframes 15m 60m
```

These are explicit range backfills, not `full` mode. Daily reads all prior
`stock_daily` history through the end date. Intraday reads 1m source history
through the end date. Both calculate with earlier history but upsert only the
inclusive requested range, without deleting anything. `--from-date` and
`--to-date` are equivalent aliases. `--as-of` cannot be used with a range.

### Full recomputation

```bash
python main.py features-daily --mode full --symbols SSI
python main.py features-intraday --mode full --symbols SSI --timeframes 15m 60m
```

The first reads all selected `stock_daily` history and upserts `1d`. The second
reads all selected clean 1m history and upserts closed `15m`/`60m` features.
Neither command deletes existing rows.

### Replace validation (expected to fail safely)

```bash
python main.py features-daily --mode replace --from 01/07/2026 --to 31/07/2026 --symbols SSI
python main.py features-intraday --mode rebuild-clean --from 01/07/2026 --to 31/07/2026 --symbols SSI --timeframes 15m
```

These commands demonstrate valid scope only. They currently validate the one
symbol/timeframe/range request, then return an error saying atomic replace is
not configured. No data is read for calculation, written, or deleted.

The compatibility command remains available for mixed persisted timeframes:

```bash
python main.py features --mode incremental --date 31/07/2026 --symbols SSI --timeframes 15m 60m 1d
```

Prefer the source-specific commands above when operating only daily or
intraday features. To collect 1m source candles, use the separate ingest command:

```bash
python main.py intraday-ingest 31/07/2026 --symbols SSI
```

## Features currently calculated

All persisted rows contain OHLCV/value where available and the following
groups. Early rows can legitimately be `NULL` until enough warm-up exists.

### Shared by daily and intraday

- **Price and returns:** `return_from_open`, `return_from_prev_close`; measure
  movement from the session open and previous daily close.
- **Trend:** `ema9`, `ema20`, `ema50`, `ema9_above_ema20`,
  `ema20_above_ema50`; summarize direction and EMA alignment.
- **Momentum:** `rsi14`, `macd`, `macd_signal`, `macd_histogram`; summarize
  speed and direction of price movement.
- **Liquidity:** `volume_ma20`, `volume_ratio`, `value_ma20`, `value_ratio`;
  compare current activity with a 20-observation baseline.
- **Price range/breakout:** `high_20_bars`, `low_20_bars`,
  `close_above_high_20`, `close_below_low_20`; compare the close with the prior
  20 bars without including the current bar.
- **Candle shape:** `candle_range`, `candle_body`, `candle_body_pct`,
  `close_position_in_candle`; describe the bar's range, body, and close location.

### Daily-specific behavior

Daily rows use daily OHLCV/value from `stock_daily`. Intraday-only fields
`return_1m`, `return_5m`, `return_15m`, `vwap_intraday`, `close_above_vwap`, and
`distance_to_vwap_pct` are `NULL` for `1d` output.

### Intraday-specific behavior

- `return_1m`, `return_5m`, and `return_15m` represent applicable same-session
  wall-clock returns; fields shorter than the output bar are `NULL` when not
  meaningful (for example, 1m/5m returns on a 15m row).
- `vwap_intraday`, `close_above_vwap`, and `distance_to_vwap_pct` describe
  position relative to estimated intraday VWAP, which resets each trading date.
- 15m/60m volume and value are sums of their clean 1m source candles.
- Intraday `volume_ma20`/`value_ma20` compare the same local-time bucket across
  prior observed dates. `return_from_open` uses official `stock_daily` open
  context when available.

Missing inputs remain `NULL`, not zero. Clean intraday `value` is currently an
estimate based on `round(close * volume)`, so its derived value/VWAP features
share that provenance.

## Verify a run

First read the command summary: check `status`, `total_records`,
`records_by_timeframe`, and per-symbol errors. Then use read-only SQL against
the current schema. Adjust the symbol and UTC timestamps to the requested
Vietnam-market interval.

```sql
-- Confirm symbol, timeframe, requested interval, and newest persisted row.
select symbol, timeframe, min(time) as first_time, max(time) as latest_time,
       count(*) as row_count
from public.features
where symbol = 'SSI'
  and timeframe in ('1d', '15m', '60m')
  and time >= '2026-07-01T00:00:00Z'
  and time <  '2026-08-01T00:00:00Z'
group by symbol, timeframe
order by symbol, timeframe;

-- The actual feature key must have no duplicates.
select symbol, timeframe, time, count(*)
from public.features
group by symbol, timeframe, time
having count(*) > 1;

-- Inspect expected and suspicious NULLs near the latest rows.
select symbol, timeframe, time, close, ema50, rsi14, macd,
       volume_ma20, vwap_intraday
from public.features
where symbol = 'SSI' and timeframe = '15m'
order by time desc
limit 20;

-- Confirm the latest feature watermark for each persisted stream.
select symbol, timeframe, max(time) as watermark
from public.features
where symbol = 'SSI'
group by symbol, timeframe
order by timeframe;
```

Interpret NULLs with context: early EMA/RSI/MACD/20-bar rows may lack warm-up;
all intraday-return and VWAP columns are expected to be `NULL` on `1d`; missing
required keys or a long-established indicator unexpectedly becoming `NULL`
deserves investigation.

## Common problems

- **No clean source rows:** run and validate the separate daily or intraday
  ingest first. Features never fabricate missing source data.
- **Wrong timeframe:** use `features-daily` for `1d` and
  `features-intraday --timeframes 15m 60m` for intraday output.
- **Expecting `1m`/`5m` in `features`:** 1m is a clean source timeframe and 5m
  is not a persisted production feature timeframe. Their rejection is expected.
- **Treating full as delete + rebuild:** full only upserts; it cannot remove
  stale rows outside its computed result.
- **NULL indicators at the beginning:** rolling calculations need warm-up.
  Verify source history before treating early NULLs as an error.
- **Replace rejected:** it requires exactly one symbol, one timeframe, and both
  bounds; even valid scope stops safely because atomic replace is unavailable.
- **Supabase failure:** install dependencies and provide `SUPABASE_URL` plus the
  appropriate Supabase key through the environment. Never put credentials in
  commands, logs, or this documentation.

## Package map

| File | Responsibility |
| --- | --- |
| `daily.py` | Read `stock_daily`, calculate `1d`, and write `features`. |
| `intraday.py` | Read 1m candles, aggregate closed buckets, and calculate intraday features. |
| `backfill.py` | Calculate an inclusive historical range and write only that range. |
| `common.py` | Shared formulas and dataframe preparation. |
| `runtime.py` | DB reads, watermarks, warm-up windows, serialization, upsert, replace guard, and summaries. |
| `runner.py` | Compatibility orchestration for mixed sources. |
| `policy.py` | Public persisted-timeframe defaults and rejection of 1m/5m writes. |

## Database and data impact of this guide

Documentation changes require no migration, database write, source-data
backfill, or feature backfill. Existing `1m`/`5m` feature rows, if any, are not
automatically removed; cleanup would require a separate reviewed operation.
