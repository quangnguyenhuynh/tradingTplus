# TradingTPlus CLI guide

[Tiếng Việt](CLI_USAGE.vi.md) · Run from the directory containing `main.py`.
Example dates/symbols are illustrative; replace them with the intended data scope.

## Start with your goal

| Goal | Recommended command | Effect |
| --- | --- | --- |
| Rank foreign attention/net buying/net selling | `foreign-rank` | Read-only RPC |
| Read SSI foreign history | `foreign-symbol` | Read-only RPC |
| Prepare foreign metrics | `foreign-features-preview` → `foreign-features-backfill` → `foreign-features-check` | Only backfill writes features |
| Fetch stock EOD and check completeness | `stock-eod` | Writes daily raw/clean |
| Fetch intraday and check completeness | `stock-intraday` | Writes raw/clean 1m |
| Fill missing daily history | `backfill-daily` | Writes daily raw/clean |
| Calculate stock daily technical metrics | `features-daily` | Writes stock 1d features |
| Preview SSI VNINDEX data | `index-preview` | Read-only SSI |
| Ingest index daily data | `index-daily` / `index-backfill` | Writes index raw/clean |
| Calculate index technical metrics | `index-features-daily` / `index-features-backfill` | Writes index features |
| Research similar historical days for T+ | `analogs` | Separate research workflow |

You do not need every command group. For foreign activity, start with
[the foreign guide](#foreign-eod). `refill` also runs intraday and technical features;
it is not a prerequisite for foreign reports.

## Contents

- [Foreign: prepare, run, interpret](#foreign-eod)
- [Dates, scope, and status](#conventions)
- [Master data](#master-data)
- [Stock source ingest](#stock-source)
- [Source backfill and refill](#source-backfill)
- [Stock technical features](#stock-features)
- [Index source and features](#index-data)
- [Historical Analog](#analog)
- [Advanced streaming](#streaming)
- [Environment variables](#environment)

## Reading examples

`bash` blocks contain examples to copy after choosing your dates/symbols.
`text` blocks with `[...]`, `DATE`, or `COMMAND` describe syntax;
do not paste their brackets literally. `--help` shows options without running a pipeline:

```bash
python main.py --help
python main.py foreign-rank --help
```

<a id="foreign-eod"></a>

## Foreign EOD: from source data to rankings

These commands describe foreign trading activity; they do not run Analog/T+ backtests.
Source values stay in `stock_daily`; derived 5/20-session metrics are stored in
`stock_foreign_features_daily`. Report commands call the RPCs shared with web/mobile.

### Choose a foreign command

| Goal | Command | Database write? |
| --- | --- | --- |
| Calculate one symbol/date for inspection | `foreign-features-preview` | No |
| Calculate and save a target date | `foreign-features-daily` | Foreign features only |
| Calculate and save a date range | `foreign-features-backfill` | Foreign features only |
| Recalculate and compare stored features | `foreign-features-check` | No |
| Read rankings | `foreign-rank` | No; RPC |
| Read one symbol's history | `foreign-symbol` | No; RPC |

### First-time prerequisites

1. Follow the root README for environment setup; run from the directory containing
   `main.py`. Foreign commands require DB access, not SSI access.
2. Review and manually deploy
   [20260907_create_stock_foreign_features_daily.sql](../migrations/20260907_create_stock_foreign_features_daily.sql)
   if needed. It creates the feature table and two RPCs; CLI does not apply migrations.
3. Verify foreign fields and turnover in `stock_daily` for the desired scope.
   If source is missing, run a separate scoped `backfill-daily` and inspect its result.
4. Prepare a verified `calendar.json` for the correct market and range. Include
   19 sessions before the first output date for full 20D metrics.
   Comparing consecutive five-session windows requires ten source sessions.

Calendar JSON requires `source`, `market`, and `sessions`. This is only a shape
example, **not a complete backfill calendar**:

```json
{"source":"Operator-verified calendar source","market":"HOSE","sessions":["2026-08-27","2026-08-28"]}
```

Calendar entries use `YYYY-MM-DD`; foreign CLI dates use `DD/MM/YYYY`.
Supply complete, unique real sessions. The current reader trusts the operator's
verification; it does not independently check exchange sessions or each symbol's market.
Without `--calendar-file`, calculations return `PARTIAL / WINDOW_UNVERIFIED`.
Rank/history commands do not accept a calendar option.

### Preview, save, check, then read

Replace the illustrative dates/symbols with your actual source scope.
`calendar.json` below is your prepared file, not a bundled repository file.

```bash
# 1. Calculate without writes
python main.py foreign-features-preview --symbol SSI --date 28/08/2026 --calendar-file calendar.json

# 2. Save the range after inspecting preview
python main.py foreign-features-backfill --from 03/08/2026 --to 28/08/2026 --symbols SSI --calendar-file calendar.json

# 3. Compare source-derived and stored features
python main.py foreign-features-check --from 03/08/2026 --to 28/08/2026 --symbols SSI --calendar-file calendar.json

# 4. Read net buying and symbol history
python main.py foreign-rank --date 28/08/2026 --ranking accumulation --window 5 --symbols SSI --top 20
python main.py foreign-symbol --symbol SSI --date 28/08/2026 --lookback 20
```

Preview always prints JSON; the accepted `--json` flag currently does not change rendering.
Check reports `missing_features` and `stale` when recalculated rows are available.
Read `rows[].quality_status` as well: summary `status=OK` does not prove every
5/20-session metric is complete. Warm-up rows can be stored with NULL metrics.

### Daily updates and repairs

```bash
# Default mode=target: save only this date
python main.py foreign-features-daily --date 28/08/2026 --symbols SSI SHB --calendar-file calendar.json

# Inspect up to 20 sessions ending at the target; save new/changed fingerprints
python main.py foreign-features-daily --date 28/08/2026 --symbols SSI SHB --mode incremental --calendar-file calendar.json
```

Incremental currently examines only the last 20 calendar sessions, not all history.
Older corrections need an explicit range backfill. Changing source date D can
affect D and the next 19 sessions. Backfill writes only its requested range;
inspect `affected_after_range` and check/rebuild later affected dates.
That list is limited to sessions supplied in the calendar.

Preview takes one `--symbol`. Daily/backfill/check/rank accept `--symbols SSI SHB`;
omitting it uses current active symbols. Do not supply an empty flag.
The service reports unknown/inactive symbols; ranking intersects scope with active symbols.
Daily requires `--date`; backfill/check require `--from` and `--to`.
Foreign commands currently have no `--from-date`/`--to-date` aliases.

### Select a ranking

| `--ranking` | Meaning | `--window` |
| --- | --- | --- |
| `attention` | Largest foreign buy + sell activity | 1, 5, 20 |
| `accumulation` | Strongest net buying, positive first descending | 1, 5, 20 |
| `distribution` | Strongest net selling, most negative first | 1, 5, 20 |
| `emerging` | Activity increase over the previous five sessions | Only 5 |

```bash
python main.py foreign-rank --date 28/08/2026 --ranking attention --window 1 --top 20
python main.py foreign-rank --date 28/08/2026 --ranking accumulation --window 20 --sort value --top 20
python main.py foreign-rank --date 28/08/2026 --ranking distribution --window 5 --sort ratio --market HOSE --top 20
python main.py foreign-rank --date 28/08/2026 --ranking emerging --window 5 --sort ratio --top 20
python main.py foreign-rank --date 28/08/2026 --ranking attention --window 5 --top 20 --offset 20
```

- `--ranking` and `--date` are required.
- `--window` defaults to 5; `--sort` defaults to `value`, alternatively `ratio`.
- `--top` defaults to 20, RPC range 1..100; `--offset` defaults to 0 and must be nonnegative.
- `--market` matches master values; `--symbols` further narrows scope.
- History `--lookback` defaults to 20, RPC range 1..100. It limits available daily
  rows ending at the selected date, not elapsed calendar days.
- 1D rankings do not require a 20D feature backfill, but do require the deployed
  RPC and valid source. 5/20D rankings read stored features.
- `emerging --sort value` currently also needs the earlier 5D feature row in DB;
  calculating only the final target date may not be sufficient.

### Interpret output and current limitations

Reports return `{meta, rows}`. Inspect date, scope, `data_status`, counts, and
the selected metric. Current active symbols are not necessarily the whole market.
Money is VND. Ratios are fractions: 0.05 = 5%; a change of 0.02 = 2 percentage points.
Activity sums both foreign sides, not unique turnover. NULL is not zero.
Equal metric values share rank; symbol provides stable pagination order.

**Current executable limitations:**
- RPC does not recompute fingerprints against the full source window at query time.
  `freshness=CURRENT` does not prove historical inputs are unchanged.
  Check also does not fully cover orphan rows when a target source is missing/uncalculable.
- `eligible_count/coverage_ratio` are counted before excluding NULL selected metrics,
  so coverage can be overstated. Do not use coverage alone as a completeness guarantee.
- RPC requires valid target-day turnover even for value sorting.
- After source corrections/deletions, inspect and rebuild the affected scope before
  relying on reports. An OK summary does not resolve these implementation limitations.

### Troubleshooting

| Symptom | Next check/action |
| --- | --- |
| `WINDOW_UNVERIFIED` | Supply a verified calendar covering the required sessions |
| `INSUFFICIENT_HISTORY` or NULL metrics | Inspect calendar/source warm-up; never substitute zero |
| `MISSING_SOURCE` in quality | Inspect each expected source session; ingest missing source separately |
| `missing_features > 0` | Backfill the feature scope, then check again |
| `stale > 0` | Rebuild affected dates, including up to 19 sessions after a source repair |
| `rows=[]` | Check active scope, date, window, metric, and buying/selling direction |
| Missing table/function | Verify migration deployment in the intended DB |
| RPC permission denied | Verify EXECUTE and source SELECT/RLS; never put the service key in an app |

CLI uses backend credentials; successful CLI access does not verify web/mobile permissions.
The migration does not automatically grant all source-table client privileges.
See [foreign specification](FOREIGN_EOD_FEATURES.md) for formulas and the
[migration](../migrations/20260907_create_stock_foreign_features_daily.sql) for permission checks.
The executable limitations above take precedence over stronger design-document claims.

<a id="conventions"></a>

## Safety, status, and common conventions

- Stock/foreign CLI dates use `DD/MM/YYYY`; index also accepts `YYYY-MM-DD`.
  Feature and source backfill bounds are inclusive.
- Symbols are space-separated, trimmed, uppercased, and deduplicated.
  Omitting `--symbols` uses each command's default scope. An explicitly empty flag
  fails parsing or normalization; it does not mean all symbols.
  Streaming is different: omitted symbols/indexes mean no subscriptions for that scope.
- Unless stated otherwise, commands print a JSON summary. Inspect its `status`:
  exit `0` includes `OK`, `PARTIAL`, `EMPTY`, Analog `dry_run`, `blocked`, and
  `apply_requires_database`; exit `1` means `FAILED` or a runtime exception;
  exit `2` means parser/validation errors. Exit `0` alone is not proof that data
  was written or an operation was applied.
- Source ingest never starts features, signals, backtests, or Analogs. Feature
  commands never start signals, backtests, or Analogs. No command implicitly
  advances the explicit Historical Analog workflow.
- Ingest needs SSI and DB access; features and foreign reports need DB access only.
  Never put real credentials on a command line or in documentation.

## Technical and Analog workflow (when needed)

```text
sync-master-data (or init)
→ daily / intraday-ingest, or stock-eod, or a scoped source backfill
→ inspect validation/completeness JSON
→ run features-daily and/or features-intraday explicitly
→ inspect feature summaries
→ Historical Analog analysis only under an approved, database-backed workflow
```

The retired rule-based CLI path has been removed; `analogs` is the only Phase 1 command tree.

<a id="master-data"></a>

## Master data

### `sync-master-data` and alias `init`

```text
python main.py sync-master-data
python main.py init
```

Example: `python main.py sync-master-data`. Both forms have no options and call
the same idempotent master-data synchronization. They read SSI master data and
write supported master tables. They do not ingest price history, calculate
features, or run signals, backtests, or Analogs.

<a id="stock-source"></a>

## Source-data ingest

### `daily`

```text
python main.py daily [DATE] [--symbols SYMBOL [SYMBOL ...]]
```

Example: `python main.py daily 07/08/2026 --symbols SSI HPG`.

- `DATE` is an optional positional `DD/MM/YYYY`. Omitted means the latest
  **previous** weekday in Vietnam time (not a verified exchange trading day).
- `--symbols` is optional and requires one or more values when supplied.
  Omitted means all active master symbols; supplied values restrict that scope.

It reads SSI `DailyStockPrice`, writes traceable `stock_raw_daily` and canonical
`stock_daily`, and may update existing conflict-key rows. It does not delete
scope data, ingest intraday/index history, or run completeness, features,
signals, backtests, or Analogs.

### `intraday-ingest`

```text
python main.py intraday-ingest [DATE] [--symbols SYMBOL [SYMBOL ...]]
```

Example: `python main.py intraday-ingest 07/08/2026 --symbols SSI`.
`DATE` and `--symbols` have the same required/omitted behavior as `daily`.
It reads SSI `IntradayOhlc` at resolution 1 and writes `stock_raw_intraday` plus clean
`stock_intraday` rows with persisted `timeframe='1m'`. It may read `stock_daily`
for daily context. It does not write aggregate candles or run daily ingest,
completeness, features, signals, backtests, or Analogs.

### `stock-eod`

```text
python main.py stock-eod [DATE] [--symbols SYMBOL [SYMBOL ...]]
```

Example: `python main.py stock-eod 07/08/2026 --symbols SSI HPG`.

- Omitted `DATE` means the latest weekday **on or before today** in Vietnam
  time. This differs from `daily`/`intraday-ingest`, which select the previous
  weekday. Neither rule proves the date is an exchange trading session.
- Omitted `--symbols` means rows with `status=active`; supplied values are intersected with this daily scope.

It writes only daily raw/clean data and runs daily-only completeness. The deprecated `intraday_summary` key is `null`; it does not run intraday, index, or downstream computation.

### `stock-intraday`

```text
python main.py stock-intraday [DATE] [--symbols SYMBOL [SYMBOL ...]]
```

Fetches only SSI `IntradayOhlc` resolution 1, writes raw and canonical 1m source data, then runs intraday-only completeness. It does not ingest daily/index data or run features, signals, backtests, or Analog. Automatic and explicit workflow scope requires both `symbols.status='active'` and `intraday_status='active'`; ignored values are reported. Omitted date uses the latest weekday on or before today in Vietnam.

<a id="source-backfill"></a>

## Source-data backfill

Shared syntax (`--from-date`/`--to-date` are exact aliases):

```text
python main.py COMMAND --from DD/MM/YYYY --to DD/MM/YYYY [--symbols SYMBOL [SYMBOL ...]]
python main.py COMMAND --from-date DD/MM/YYYY --to-date DD/MM/YYYY [--symbols ...]
```

`--from` and `--to` are both required, mutually dependent inclusive bounds;
start must not follow end. `--symbols` is optional but needs at least one value
when present. Omitted means all active master symbols; supplied values use that
same scope for each date. Weekends are skipped; an empty weekday response stays
observable and is not fabricated.

| Command | Exact example | Reads/writes |
| --- | --- | --- |
| `backfill-daily` | `python main.py backfill-daily --from 03/08/2026 --to 07/08/2026 --symbols SSI` | Writes daily raw/clean source data only; no intraday or completeness. |
| `backfill-intraday` | `python main.py backfill-intraday --from-date 03/08/2026 --to-date 07/08/2026 --symbols SSI` | Writes raw/clean 1m intraday source data only; no daily or completeness. |
| `backfill` | `python main.py backfill --from 03/08/2026 --to 07/08/2026 --symbols SSI HPG` | Runs daily and intraday ingest plus completeness for each included date. |

All three may upsert existing source rows. They do not run feature backfill,
signals, backtests, or Analogs and do not perform a scoped delete/replace.

### `refill`

```text
python main.py refill --symbol SSI --from DD/MM/YYYY --to DD/MM/YYYY
python main.py refill --symbol SSI --from-date DD/MM/YYYY --to-date DD/MM/YYYY
```

This explicit maintenance orchestrator requires exactly one non-blank,
non-`ALL` symbol; it trims and uppercases the value. It runs daily then 1m
intraday source backfill and completeness before invoking the existing range
feature runners for `1d`, `15m`, and `60m`. It uses upsert only: no delete,
replace, master sync, aggregate source-candle write, signal, backtest, or Analog.
Source `PARTIAL` still runs features and remains final `PARTIAL`; source `FAILED`
skips features. Feature branches run independently. A weekend-only range is an
`OK` no-op. Exit codes are `0` for `OK`/`PARTIAL`, `1` for `FAILED`, and `2` for
invalid arguments.

<a id="stock-features"></a>

## Feature data policy and modes

`stock_features` persists only `1d`, `15m`, and `60m`:

| Timeframe | Canonical source | Behavior |
| --- | --- | --- |
| `1d` | `stock_daily` | Daily T+ context; never derived from intraday. |
| `15m`, `60m` | clean `stock_intraday` 1m | Session-aware in-memory aggregation; aggregate candles are not written back. |

Writes for `1m` and `5m` features are rejected. Intraday features also read
`stock_daily` for official-open/previous-close context and persist closed
buckets only.

- `incremental`: uses an independent symbol/timeframe watermark and bounded
  warm-up (five years for daily; 250 observed source sessions for intraday).
  With no watermark, only output in the requested target scope is written.
- explicit range: `--from` plus `--to` invokes inclusive feature backfill and
  uses warm-up before the range, but writes only range output.
- `full`: reads all selected history, recalculates it, and **upserts** every
  result. It never deletes stale rows and is not replace.
- `replace` and alias mode `rebuild-clean`: calculate and validate first, then
  call the deployed atomic RPC to delete/replace one exact scope. They require
  exactly one non-wildcard symbol, one persisted timeframe, and an explicit
  valid `--from`/`--to` range. They reject `--date` and require the atomic RPC
  migration to be deployed.

Incremental processing cannot discover arbitrary old source corrections without
version metadata; use an exact, reviewed replace when historical correction is
required.

### `features-daily`

```text
python main.py features-daily [--mode incremental|full|replace|rebuild-clean]
  [--date DD/MM/YYYY] [--from DD/MM/YYYY --to DD/MM/YYYY]
  [--symbols [SYMBOL ...]]
```

Examples:

```bash
python main.py features-daily --date 07/08/2026 --symbols SSI HPG
python main.py features-daily --from 03/08/2026 --to 07/08/2026 --symbols SSI
python main.py features-daily --mode full --symbols SSI
python main.py features-daily --mode replace --from 03/08/2026 --to 07/08/2026 --symbols SSI
```

`--mode` is optional, default `incremental`. In incremental mode exactly one of
`--date` or the `--from`+`--to` pair is required; they cannot be combined.
`full` forbids date/range. Replace modes require range as described above.
`--from-date` and `--to-date` are aliases. Omitted `--symbols` means all eligible symbols except in exact replace.
An explicitly empty flag is rejected; supplying symbols restricts computation. This command reads only `stock_daily`, writes
only `stock_features` at `1d`, and does not ingest or run signals/backtests/Analogs.

### `features-intraday`

```text
python main.py features-intraday [--mode incremental|full|replace|rebuild-clean]
  [--date DD/MM/YYYY] [--from DD/MM/YYYY --to DD/MM/YYYY]
  [--symbols [SYMBOL ...]] [--timeframes [15m 60m]] [--as-of CUTOFF]
```

Examples:

```bash
python main.py features-intraday --date 07/08/2026 --symbols SSI --timeframes 15m 60m
python main.py features-intraday --date 07/08/2026 --as-of 14:30 --symbols SSI
python main.py features-intraday --mode full --symbols SSI --timeframes 60m
python main.py features-intraday --mode rebuild-clean --from 03/08/2026 --to 07/08/2026 --symbols SSI --timeframes 60m
```

Date/range/mode constraints and aliases match `features-daily`. `--timeframes`
is optional/repeatable by value and defaults to `15m 60m`; supplying it selects
only persisted intraday timeframes. `--as-of` is optional and accepts `HH:MM`
Vietnam time or a timezone-aware timestamp; omitted uses all closed buckets in
the target scope. It cannot be combined with a range. This command reads clean
1m source data, aggregates in memory, and writes closed `15m`/`60m` feature
rows. It does not ingest, write aggregate source candles, or run downstream
signals/backtests/Analogs.

### `features` compatibility router

```text
python main.py features [--mode incremental|full] [--date DD/MM/YYYY]
  [--symbols [SYMBOL ...]] [--timeframes [15m 60m 1d]]
```

Example: `python main.py features --date 07/08/2026 --symbols SSI --timeframes 1d 15m 60m`.
`--mode` defaults to `incremental`; `--timeframes` defaults to `15m 60m 1d`;
omitted symbols mean all eligible symbols. `--date` is an optional target for
incremental routing; supplying it restricts output to that date. Full mode
recomputes/upserts selected history without deleting. This compatibility router
writes `stock_features` only; prefer source-specific commands for explicit range or
replace. It runs no ingest, signals, backtests, or Analogs.

### `intraday` legacy feature alias

```text
python main.py intraday [--snapshot-time VALUE] [--symbols [SYMBOL ...]]
  [--timeframes [15m 60m]]
```

Example: `python main.py intraday --snapshot-time 14:30 --symbols SSI --timeframes 15m`.
Omitted symbols mean all eligible symbols and omitted timeframes default to
`15m 60m`. `--snapshot-time` defaults to current Vietnam time for summary
metadata; supplying it currently changes that summary marker but is **not** a
safe source/bucket cutoff. Use `features-intraday --date ... --as-of ...` for a
cutoff. This alias calculates incremental intraday features; it does not ingest
candles or run signals/backtests/Analogs.

<a id="index-data"></a>

## Index Daily source data

```bash
python main.py index-preview (--date DATE | --from DATE --to DATE) --indexes VNINDEX[,HNXINDEX] [--raw | --json]
python main.py index-daily [YYYY-MM-DD|DD/MM/YYYY] [--indexes VNINDEX VN30]
python main.py index-backfill --from YYYY-MM-DD|DD/MM/YYYY --to YYYY-MM-DD|DD/MM/YYYY [--indexes VNINDEX VN30]
python main.py index-check [YYYY-MM-DD|DD/MM/YYYY] [--indexes VNINDEX VN30]
python main.py index-features-preview --date YYYY-MM-DD|DD/MM/YYYY [--indexes VNINDEX VN30]
python main.py index-features-daily --date YYYY-MM-DD|DD/MM/YYYY [--indexes VNINDEX VN30]
python main.py index-features-backfill --from YYYY-MM-DD|DD/MM/YYYY --to YYYY-MM-DD|DD/MM/YYYY [--indexes VNINDEX VN30]
python main.py index-features-check --from YYYY-MM-DD|DD/MM/YYYY --to YYYY-MM-DD|DD/MM/YYYY [--indexes VNINDEX VN30]
```

### Read-only `index-preview`

`index-preview` calls SSI `DailyIndex`, applies the current normalization mapper,
and prints the result for inspection. It does not construct a database client,
read database scope, or write `index_raw_daily`, `index_daily`, or any other raw
or clean table. It also does not calculate features or research outputs.

The command accepts exactly one date selection:

- `--date DATE` previews one date.
- `--from DATE --to DATE` previews every calendar date in the inclusive range;
  `--to` is required with `--from`.
- Each date accepts `YYYY-MM-DD` or `DD/MM/YYYY`.
- `--indexes` is required and takes one comma-separated value such as
  `VNINDEX,HNXINDEX`. Unlike the ingest, backfill, and check commands, omitting
  it is an argument error; preview never resolves index codes from
  `index_master`.
- Human-readable output is the default and includes a field-count/omission
  summary for each SSI item. `--raw` prints complete SSI payload rows plus that
  mapping summary as JSON, while `--json` prints complete normalized clean rows
  (including nullable keys) as JSON. The two flags are mutually exclusive.

Examples:

```bash
# One date (DD/MM/YYYY is also accepted)
python main.py index-preview --date 2026-08-24 --indexes VNINDEX

# Inclusive date range and multiple indexes
python main.py index-preview --from 2026-08-23 --to 2026-08-24 --indexes VNINDEX,HNXINDEX

# Raw SSI payload wrapper
python main.py index-preview --date 2026-08-24 --indexes VNINDEX --raw

# Normalized records only
python main.py index-preview --date 24/08/2026 --indexes VNINDEX --json
```

The default display has this shape (values shown are illustrative):

```text
index_code | trading_date | index_value | change | ratio_change | total_vol | total_val | source | status
----------------------------------------------------------------------------------------------------------------
VNINDEX | 2026-08-24 | 1245.5 | - | 0.25 | 123456 | - | SSI_DailyIndex | OK
```

Missing source values remain JSON `null` and display as `-`. If SSI returns no
rows, preview exits successfully and prints a clear message such as
`No SSI index daily data returned for VNINDEX on 2026-08-24`; it does not
fabricate a row.

The field-by-field raw/clean contract and accepted aliases are documented in
[SSI DailyIndex field mapping](SSI_DAILY_INDEX_MAPPING.md). `Time` and unknown
source keys are preserved raw and reported as omitted from clean; they are not
silently removed or assigned invented clean meanings.

All date arguments for the four index commands accept exactly `YYYY-MM-DD` or `DD/MM/YYYY`; for example, `2026-08-24` and `24/08/2026` identify the same date. Other separators such as `24-08-2026` are rejected.

### Choosing the index command

- **Preview:** `index-preview` calls SSI and renders raw or normalized data;
  it neither reads nor writes the database.
- **Daily ingest:** `index-daily` fetches one resolved trading date and writes
  payload evidence to `index_raw_daily` before validated normalized rows in
  `index_daily`. When its date is omitted, it uses the latest weekday on or
  before the current Vietnam date, so the scheduled post-market `index-eod`
  run targets the current date Monday through Friday and the prior Friday on a
  weekend. This is only a calendar rule, not proof of a Vietnam exchange
  trading session; holidays and empty SSI responses never produce fake rows.
- **Backfill:** `index-backfill` runs that source-data ingest for an inclusive
  historical range.
- **Completeness:** `index-check` reads the database and compares expected index
  scope with raw and clean rows; it does not fetch preview data or write rows.

For `index-daily`, `index-backfill`, and `index-check`, omitting `--indexes`
resolves only `status = 'active'` codes from `index_master`. Explicit codes are
validated against the complete master and may intentionally target an inactive
row; unknown explicit codes fail. Stock ingest follows the same rule through
`symbols`: omitted scope uses active rows, while explicit symbols remain
available for maintenance/backfill. The independent index-eod pipeline runs index ingest and its separate
completeness stage. None of these commands calculate features or research
outputs.

Recommended workflow:

1. Run `index-preview` to inspect the SSI response.
2. Verify the returned fields, dates, index codes, and values.
3. Run `index-daily` for one date or `index-backfill` for an inclusive range.
4. Run `index-check` for completeness.

### Separate index feature calculation

After manually applying `20260826_create_index_features_daily.sql`, use the four
`index-features-*` commands above. Preview calculates from the database but never
writes; daily and backfill upsert only `index_features_daily`; check compares
eligible clean dates with feature identities and reports missing/duplicate dates,
pre-warm-up rows, unexpected post-warm-up nulls, raw-without-clean dates, and
insufficient histories. Ingestion never invokes these commands, and these
commands never invoke ingestion or downstream research. For formulas, null
rules, the 250-session warm-up, and backfill order, see
[`src/index_features/README.md`](../src/index_features/README.md).

<a id="analog"></a>

## Historical Analog EOD V1 runtime

EOD V2 uses the same commands with `--version 2` and its exact config hash. To
register it explicitly: `python main.py analogs profiles register --profile
TPLUS_ANALOG_CORE_EOD --version 2 [--apply]`. V2 remains draft, so production query/daily commands are blocked pending its own history,
calibration, final validation, and approval.

```bash
python main.py analogs profiles list
python main.py analogs profiles register [--apply]
python main.py analogs history build --profile TPLUS_ANALOG_CORE_EOD --version 1 --config-hash <exact-hash> --symbols SSI --from DD/MM/YYYY --to DD/MM/YYYY --mode full [--apply]
python main.py analogs query --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbol SSI --date DD/MM/YYYY --checkpoint EOD [--apply]
python main.py analogs inspect --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbol SSI --date DD/MM/YYYY --checkpoint EOD --distance-threshold 0.5
```

History is source-read/dry-run by default and persists snapshots/outcomes only with `--apply`; replace also requires `--confirm-replace`. Query always reads persisted evidence and writes audit rows only with `--apply` and an exact approved profile. Matching selects the nearest configured `top_k`; the inspect threshold option remains only as an ignored compatibility input.

<a id="streaming"></a>

## Bounded streaming ingest

```text
python main.py streaming-ingest [--symbols [SYMBOL ...]] [--indexes [INDEX ...]]
  --channels {securities-status,quote,trade,foreign-room,index,realtime-bar} [...]
  [--timeout SECONDS] [--max-messages-per-channel COUNT] [--write] [--debug]
```

Example (read-only):

```bash
python main.py streaming-ingest --symbols SSI --indexes VNINDEX \
  --channels quote index --timeout 60 --max-messages-per-channel 1 --debug
```

`--channels` is required and accepts one or more listed channel groups.
`--symbols`/`--indexes` default to empty; supplying them creates explicit
uppercase subscriptions. Channel/scope compatibility is validated. `--timeout`
defaults to `60` and must be 1..3600 seconds. `--max-messages-per-channel`
defaults to `1` and must be 1..1000. `--debug` defaults false and prints
sanitized summaries. Without `--write` the command receives and validates data
but is read-only; `--write` persists raw frames and valid normalized snapshot
rows. It is bounded and does not run source batch ingest, features, signals,
backtests, or Analogs.

<a id="environment"></a>

## Environment variables

`.env` is loaded when configuration is imported. Unset required credentials
have no fallback.

| Variable | Default | CLI use |
| --- | --- | --- |
| `SUPABASE_URL` | none | Database endpoint for ingest, features, streaming writes, and Historical Analog DB operations. |
| `SUPABASE_SERVICE_KEY` | none | Service credential used by the database client. |
| `SUPABASE_KEY` | none | Loaded compatibility key; the current database client uses the service key. |
| `SSI_CONSUMER_ID` | none | SSI REST/streaming authentication. |
| `SSI_CONSUMER_SECRET` | none | SSI REST/streaming authentication. |
| `SSI_STREAMING_BASE_URL` | `https://fc-datahub.ssi.com.vn/` | SignalR base URL for `streaming-ingest`. |
| `SSI_SIGNALR_PATH` | `v2.0/signalr` | SignalR path. |
| `SSI_SIGNALR_HUB` | `FcMarketDataV2Hub` | SignalR hub name. |
| `SSI_SIGNALR_RECEIVE_METHOD` | `Broadcast` | Incoming SignalR method. |
| `SSI_SIGNALR_SWITCH_METHOD` | `SwitchChannels` | Subscription method. |
| `SSI_STREAMING_ENABLED` | `true` | `1`, `true`, `yes`, or `y` enables streaming; other values disable it. |
| `ORDERBOOK_SNAPSHOT_TIMEOUT_SEC` | `20` | Loaded for snapshot utilities, not the `streaming-ingest --timeout` default. |
| `SSI_ORDERBOOK_URL` | none | Optional account-specific REST order-book endpoint; not used by this CLI tree. |
| `SSI_STREAMING_URL` | none | Backward-compatible placeholder; not the SignalR connection setting. |

SSI REST endpoint constants are fixed in `src/config.py`, not environment
overrides. Vietnam market dates/session logic uses Asia/Ho_Chi_Minh semantics.

## Read-only SSI API Inspector

The standalone inspector defaults to SSI REST v3 and does not change or invoke production ingestion. Select legacy v2 explicitly; listing/help need no credentials or network:

```bash
python scripts/ssi_api_inspector/inspect.py list
python scripts/ssi_api_inspector/inspect.py list --data-source ssi_v2
python scripts/ssi_api_inspector/inspect.py run daily-stock-price --symbol SSI --date 08/09/2026 --full-json
python scripts/ssi_api_inspector/inspect.py run daily-stock-price --data-source ssi_v2 --symbol SSI --date 08/09/2026 --full-json
```

V3 uses `SSI_API_KEY`/`SSI_API_SECRET`; legacy v2 uses `SSI_CONSUMER_ID`/`SSI_CONSUMER_SECRET`. See [`scripts/ssi_api_inspector/README.md`](../scripts/ssi_api_inspector/README.md) for endpoint tables, ranges, paging versus sample limits, status/exit codes, redaction, and troubleshooting.
