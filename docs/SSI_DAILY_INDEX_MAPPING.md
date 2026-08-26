# SSI DailyIndex field mapping

This matrix documents the 23 fields in the SSI FastConnect Data `GetDailyIndex`
response audited on 2026-08-26. `index_raw_daily.payload` always contains the
complete, unchanged SSI item, including unknown future keys. Clean numeric values
are nullable and follow the project's existing `numeric`/nullable-float ingest
convention; a missing or empty source value is never changed to zero.

| SSI field (accepted aliases) | Raw location | Clean column / dimension | Decision |
|---|---|---|---|
| `Indexcode`, `indexcode`, `IndexId`, `indexid` | `index_raw_daily.payload` | `index_daily.index_code` | Daily identity; case-insensitive alias lookup. |
| `IndexValue` | payload | `index_daily.index_value` | Daily analytic value. |
| `TradingDate` | payload | `index_daily.trading_date` | Parsed daily identity and request-scope check. |
| `Time` | payload | — | Raw-only. Its semantics are not established and an empty value remains empty; no timestamp is invented. |
| `Change` | payload | `index_daily.change` | Daily analytic value. |
| `RatioChange` | payload | `index_daily.ratio_change` | Daily analytic value. |
| `TotalTrade` | payload | `index_daily.total_trade` | Liquidity measure. |
| `Totalmatchvol` | payload | `index_daily.total_match_vol` | Matched volume; lookup is case-insensitive. |
| `Totalmatchval` | payload | `index_daily.total_match_val` | Matched value; lookup is case-insensitive. |
| `TypeIndex` | payload | `index_daily.type_index` | Preserve the source-day value. Prefer `index_master` for static metadata when its master contract is expanded explicitly. |
| `IndexName` | payload | `index_daily.index_name`; static `index_master.index_name` | Preserve the source-day value; `index_master` remains the canonical static definition. |
| `Advances` | payload | `index_daily.advances` | Market breadth. |
| `Nochanges`, `NoChanges` | payload | `index_daily.no_changes` | Market breadth; both aliases are accepted. |
| `Declines` | payload | `index_daily.declines` | Market breadth. |
| `Ceiling`, `Ceilings` | payload | `index_daily.ceilings` | Market breadth; both aliases are accepted. |
| `Floor`, `Floors` | payload | `index_daily.floors` | Market breadth; both aliases are accepted. |
| `Totaldealvol` | payload | `index_daily.total_deal_vol` | Negotiated/deal volume; lookup is case-insensitive. |
| `Totaldealval` | payload | `index_daily.total_deal_val` | Negotiated/deal value; lookup is case-insensitive. |
| `Totalvol` | payload | `index_daily.total_vol` | Total volume; lookup is case-insensitive. |
| `Totalval` | payload | `index_daily.total_val` | Total value; lookup is case-insensitive. |
| `TradingSession` | payload | `index_daily.trading_session` | Daily session context. |
| `Market` | payload | `index_daily.market` | Preserve the source-day value; there is currently no `index_master.market` contract. |
| `Exchange` | payload | `index_daily.exchange`; static `index_master.exchange` | Preserve the source-day value; `index_master` remains the canonical static definition. |

## Preview audit contract

- Default output stays concise and appends a per-item `Mapping fields` summary.
- `--json` emits every normalized clean key, including keys whose values are
  `null`.
- `--raw` emits every original SSI item plus `mapping_summary`. The summary
  reports raw and normalized field counts and lists source keys omitted from the
  clean contract. `Time` and unknown future SSI fields therefore remain visible
  rather than being silently discarded.

## Migration and backfill

No migration is required: `index_daily` already contains every selected clean
column. Existing raw rows need no backfill. Clean rows produced from payloads
using singular `Ceiling` or `Floor` should be identified and rerun from
`index_raw_daily.payload` with an exact index/date scope; this is a clean-only,
non-destructive correction and must not delete or rewrite raw evidence.
