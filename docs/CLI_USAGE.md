# TradingTPlus CLI reference

This is the complete reference for the command tree registered by `main.py`.
Runtime code is authoritative when this document and older design documents
disagree. Run commands from the repository root as `python main.py ...`.

## Safety, status, and common conventions

- Dates are `DD/MM/YYYY`. Feature and source backfill bounds are inclusive.
- Symbol options accept space-separated values. Values are trimmed, uppercased,
  and deduplicated in first-seen order. Where `--symbols` uses `nargs="*"`, an
  explicitly empty list is normalized to omitted scope; source/feature commands
  then resolve all eligible database/master symbols. Ingest commands using
  `nargs="+"` reject `--symbols` with no value. Streaming is different: omitted
  `--symbols` and `--indexes` remain empty and never mean `ALL`.
- Unless stated otherwise, commands print a JSON summary. Inspect its `status`:
  exit `0` includes `OK`, `PARTIAL`, `EMPTY`, Analog `dry_run`, `blocked`, and
  `apply_requires_database`; exit `1` means `FAILED` or a runtime exception;
  exit `2` means parser/validation errors. Exit `0` alone is not proof that data
  was written or an operation was applied.
- Source ingest never starts features, signals, backtests, or Analogs. Feature
  commands never start signals, backtests, or Analogs. No command implicitly
  advances the explicit Historical Analog workflow.
- Commands that write require configured SSI/Supabase access. Never put real
  credentials on a command line or in documentation.

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

## Recommended operating order

```text
sync-master-data (or init)
→ daily / intraday-ingest, or eod, or a scoped source backfill
→ inspect validation/completeness JSON
→ run features-daily and/or features-intraday explicitly
→ inspect feature summaries
→ Historical Analog analysis only under an approved, database-backed workflow
```

The retired rule-based CLI path has been removed; `analogs` is the only Phase 1 command tree.

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

It reads SSI `DailyStockPrice`, writes traceable `raw_daily` and canonical
`stock_daily`, and may update existing conflict-key rows. It does not delete
scope data, ingest intraday/index history, or run completeness, features,
signals, backtests, or Analogs.

### `intraday-ingest`

```text
python main.py intraday-ingest [DATE] [--symbols SYMBOL [SYMBOL ...]]
```

Example: `python main.py intraday-ingest 07/08/2026 --symbols SSI`.
`DATE` and `--symbols` have the same required/omitted behavior as `daily`.
It reads SSI `IntradayOhlc` at resolution 1 and writes `raw_intraday` plus clean
`stock_intraday` rows with persisted `timeframe='1m'`. It may read `stock_daily`
for daily context. It does not write aggregate candles or run daily ingest,
completeness, features, signals, backtests, or Analogs.

### `eod`

```text
python main.py eod [DATE] [--symbols SYMBOL [SYMBOL ...]]
```

Example: `python main.py eod 07/08/2026 --symbols SSI HPG`.

- Omitted `DATE` means the latest weekday **on or before today** in Vietnam
  time. This differs from `daily`/`intraday-ingest`, which select the previous
  weekday. Neither rule proves the date is an exchange trading session.
- Omitted `--symbols` means all active master symbols; supplied values restrict
  daily ingest, intraday ingest, and completeness to the same scope.

It writes the daily and 1m raw/clean ingest layers, then reads them for
completeness and returns `OK`, `PARTIAL`, or `FAILED`. It does not calculate
features or run signals, backtests, or Analogs.

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

## Feature data policy and modes

`features` persists only `1d`, `15m`, and `60m`:

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
`--from-date` and `--to-date` are aliases. Omitted `--symbols` (or `--symbols`
with no values) means all eligible symbols except in exact replace; supplying
symbols restricts computation. This command reads only `stock_daily`, writes
only `features` at `1d`, and does not ingest or run signals/backtests/Analogs.

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
writes `features` only; prefer source-specific commands for explicit range or
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

## Historical Analog EOD V1 runtime

```bash
python main.py analogs profiles list
python main.py analogs profiles register [--apply]
python main.py analogs history build --profile TPLUS_ANALOG_CORE_EOD --version 1 --config-hash <exact-hash> --symbols SSI --from DD/MM/YYYY --to DD/MM/YYYY --mode full [--apply]
python main.py analogs query --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbol SSI --date DD/MM/YYYY --checkpoint EOD [--apply]
python main.py analogs inspect --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbol SSI --date DD/MM/YYYY --checkpoint EOD --distance-threshold 0.5
```

History is source-read/dry-run by default and persists snapshots/outcomes only with `--apply`; replace also requires `--confirm-replace`. Query always reads persisted evidence and writes audit rows only with `--apply` and an exact approved/numeric-threshold profile. The current V1 draft/null-threshold profile remains production-blocked. Inspect reads `features` 1d plus `stock_daily`, calculates in memory, and never persists; its explicit threshold is ephemeral non-production research input, not a signal or recommendation.
