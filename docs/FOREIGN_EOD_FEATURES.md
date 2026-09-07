# Foreign EOD features and reports

`stock_daily -> foreign feature command -> stock_foreign_features_daily -> RPC`
is an explicit flow; ingest never invokes it. Daily SSI fields are the sole trading
data source. No `ForeignTrading` REST endpoint is used.

## Formula V1

For verified W-session windows (W=5 or 20), B/S/N/V mean foreign buy value,
foreign sell value, validated source net value, and `total_traded_value`:

* net value = `SUM(N)`; activity value = `SUM(B+S)` (two-sided activity, not a
  unique exchange turnover);
* net ratio = `SUM(N)/SUM(V)`; activity ratio = `SUM(B+S)/(2*SUM(V))`;
* buy/sell days count N>0/N<0; zero belongs to neither;
* 5D changes subtract the preceding, non-overlapping five-session ratio from
  the current five-session ratio.

Money is VND. Ratios are fractions; multiply by 100 for percent, and multiply a
change by 100 for percentage points. NULL records incomplete fields/history or
an invalid/zero denominator. It is not zero. Exact SSI matched/deal/odd-lot
coverage has not been independently established, so ratios must retain this
limitation. The pipeline never clamps them.

## Calendar, quality, freshness, and scope

Supply `--calendar-file` with JSON such as
`{"source":"operator-verified HOSE calendar","market":"HOSE","sessions":["2026-08-27","2026-08-28"]}`.
The operator owns source, market, and date-range verification. No weekday or
per-symbol rows are treated as the calendar. Missing calendar produces
`WINDOW_UNVERIFIED`. Missing expected rows produce `MISSING_SOURCE`; proven
short history produces `INSUFFICIENT_HISTORY`. No synthetic rows are persisted.

Fingerprint V1 covers formula/calendar identity, expected session identities,
row presence, and relevant source values. RPC excludes missing/current-formula
invalid rows; check/rebuild detects source changes before publication. A source
repair at D can affect D and the next 19 verified sessions. A bounded backfill
must be followed by a later-range check/rerun when those sessions fall beyond
its output range.

Default report scope is current active symbols (`scope_basis=current_active_symbols`),
not a historical whole-exchange universe. Explicit symbols are normalized and
intersected with current master status; unknown symbols error. Every ranking is
for one requested date.

## CLI and API

See `python main.py COMMAND --help`. Preview/check/rank/history are read-only.
Daily/backfill write only the explicit output date/range after the migration.
`foreign-rank` and `foreign-symbol` call the same RPCs used by web/Flutter:

* `get_foreign_ranking`: `p_date`, `p_ranking_type`, `p_window`, `p_sort_mode`,
  `p_market`, `p_symbols`, `p_limit`, `p_offset`.
* `get_foreign_symbol_history`: `p_symbol`, `p_to_date`, `p_limit`.

Both return `{ "meta": {...}, "rows": [...] }` (illustrative shape). Money must
be serialized without app-side loss and formatted into billions only by the app.
RPCs are `SECURITY INVOKER`; anon has no execute/read, authenticated can execute
and read derived statistics, and service role writes. Invoker access also
requires the existing authenticated SELECT entitlement/RLS on `symbols` and
`stock_daily`; verify it after migration.

## Manual rollout

1. Apply `migrations/20260907_create_stock_foreign_features_daily.sql` manually.
2. Verify `stock_daily` and a calendar file for a small scope.
3. `python main.py foreign-features-preview --symbol SSI --date 28/08/2026 --calendar-file calendar.json --json`
4. `python main.py foreign-features-backfill --from 01/08/2026 --to 28/08/2026 --symbols SSI --calendar-file calendar.json`
5. `python main.py foreign-features-check --from 01/08/2026 --to 28/08/2026 --symbols SSI --calendar-file calendar.json`
6. Query `foreign-rank` and `foreign-symbol`.
7. Expand scope only after source/calendar/coverage/security verification.

Rollback commands and verification SQL are at the bottom of the migration. Do
not backfill source automatically: use the repository's explicit `backfill-daily`
command for exact missing symbols/dates after operator review. The future job
order is `stock-eod -> daily check -> foreign feature -> foreign check -> report`;
these remain separate steps.
