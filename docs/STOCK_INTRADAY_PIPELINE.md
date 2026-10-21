# SSI v3 Stock Intraday 1m — read-only preview

[Tiếng Việt](STOCK_INTRADAY_PIPELINE.vi.md) · [CLI](CLI_USAGE.md) · [Evidence report](SSI_V3_INTRADAY_PREVIEW_REPORT.md)

## Status and evidence

**READ-ONLY — SSI API requests, zero database reads/writes. Production ingest remains NOT_IMPLEMENTED.** The preview is implemented and offline-tested; SSI source semantics remain **PROVISIONAL / PARTIAL**. Live verification is **NOT_RUN** because SSI credentials are not configured. There is no captured v3 intraday response in the repository. Existing alias/envelope conventions and synthetic protocol tests are not live API evidence.

The source registry remains preview-only without a production factory. `intraday-ingest`, `stock-intraday`, `backfill-intraday`, combined `backfill` and `refill` still fail before service access. The intraday workflow has manual unavailable diagnostics only, no schedule. Historical clean 1m remains usable for explicit features; this preview does not calculate them.

## Run the preview

Use the Python 3.11 venv with `requirements.txt` installed. Set `SSI_API_KEY` and `SSI_API_SECRET` locally; Supabase credentials are unnecessary. Help/list do not require credentials or network. Run from the repository root. Dates accept YYYY-MM-DD or DD/MM/YYYY. These commands have been checked offline only; a liquid-symbol completed day such as SSI on 2026-10-19 is an illustrative investigation scope, not a claim that its response was inspected.

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --from-date 2026-10-01 --to-date 2026-10-19 --page-size 100 --max-pages 100 --limit 5
python scripts/inspectors/ssi_rest/inspect.py run intraday-ohlc --symbol SSI --date 2026-10-19 --ascending --limit 5
```

`--show-mapping` prints dictionary rules and provisional evidence. `--full-json` makes every returned raw envelope, candle, aligned clean candidate and record diagnostic available (credential redaction still applies). Normal mode shows samples; `--limit` limits display only. Errors outside the sample remain visible. Raw arrays preserve original receive order and original values; rejected rows retain their raw objects and aligned `None` candidate with explicit errors.

## Candidate SSI request contract

GET `https://api.ssi.com.vn/api/v3/data/ohlc`, with `symbol=SSI`, `from=2026/10/19 00:00:00`, `to=2026/10/19 23:59:59`, `timeFrame=1m`, `pageIndex=1`, `pageSize=10` by default in the inspector. Provider client default page size is 1000. Range bounds are constructed as inclusive complete calendar-day bounds, not asserted to be SSI-verified inclusivity. `ascending=true` is sent only when requested through native `intraday-ohlc`; the canonical dataset retains its existing rejection of ascending. Sort support, bound inclusivity and actual envelope require verification before promotion. No other timeframe, endpoint or retired-source fallback is added.

The common `ohlc_1m_params` builder is used by both provider and inspector. Dates are converted before I/O; invalid/reversed bounds and nonpositive paging parameters fail. `--max-pages` bounds data-page attempts to 100 by default (allowed 1–1000). HTTP retries remain separately bounded; pages_requested counts logical data-page attempts, not retry/auth HTTP requests.

## Pagination and failures

The 1m route downloads successive pages beginning at `--page-index` (default 1). It does **not** terminate on a short nonempty page. With no usable provider page count it requests an explicit empty terminal page; with `pagesCount` it checks the reported last page. If `totalRecord` exists, page-1 downloads must match its count. These recognized metadata names come from existing inspector code, not a newly verified SSI schema. Unknown shapes remain malformed, not empty data.

Repeated pages (including reordered repeats), wrong page identity, changing totals/page counts, inconsistent terminal counts, unexpected early empty pages and the page bound are explicit failures. HTTP/auth/network/provider/non-JSON failures keep already received pages/candles; fetched error bodies remain available when received. Page-limit/truncation is FAILED, never successful completeness. Requests from page >1 are labeled suffix scope and cannot prove whole-range coverage. `itemsCount` is retained as metadata but is not assumed to mean the total across pages.

Recognized provisional arrays include a top-level array or data/items/dataList/result array in an envelope, with bounded nesting through data/result/response. Provider failure markers are not treated as no-data. Envelope objects, including metadata and unused source fields, stay available in full output.

## Mapping and timestamp guardrails

The shared mapper is `src/contracts/intraday_preview.py`, declared by `src/contracts/mappings/ssi_v3.json` version `1.1.0-preview`, contract `1.0.0`. The adapter and inspector call the same mapper. The generic contract fields/schema are unchanged.

| Canonical field | Provisional source / handling |
| --- | --- |
| symbol | Requested symbol, checked against source symbol if present; mismatch rejects |
| time | `time` with complete source date/time and explicit Z or ±HH:MM; normalized to UTC without shifting/truncating the timestamp |
| timeframe | Constant 1m; a conflicting returned timeFrame/timeframe rejects |
| open/high/low/close | Same-named source values converted to finite floats; no scaling invented; positive prices and OHLC inequalities validated |
| volume | Same-named source value converted exactly to nonnegative integral BIGINT range; no cumulative differencing |
| value | Existing `calculate_trade_value`: int(round(close * volume)); estimated, not official turnover |
| reference_price/ceiling_price/floor_price | NULL: equivalent source/context has not been verified; no daily DB lookup |

Missing optional values remain null in mapping evidence; missing required OHLCV for record validation rejects the candidate rather than fabricating values. Unknown fields and original source `value` remain raw/unused. Non-finite, boolean, fractional-volume, negative-volume, invalid OHLC and overflowing estimated values reject with diagnostics. Existing `round` behavior is reused; this task does not alter the estimator.

**BLOCKED source semantics:** price scaling to VND/share, whether source volume is per-candle shares, timezone for naive timestamps, and bar-start versus bar-end. Numeric candidate conversion is not unit certification. Until these are evidenced, all nonempty previews are at best PROVISIONAL. No fabricated intraday fixture is claimed as evidence.

Naive datetime, date-only, time-only, epoch/other unsupported representations are rejected. Request date is never used to manufacture a candle timestamp. A separate source date/time combination is not implemented without evidence. A source date supplied alongside an aware timestamp must agree with that timestamp and requested Vietnam range. Existing historical v2 bar metadata in definitions.json is retained because v3 convention is not verified; it must not be read as proof of v3 bar convention.

## Quality and output interpretation

The report separates request/pagination, mapping/validation, structural observations and completeness. It exposes requests/pages, raw/mapped/rejected counts, source first/last received time, canonical first/last received UTC and chronological bounds, duplicate timestamp count, received-order inversions, identity/timestamp errors, missing optional/unsupported fields, OHLCV errors and estimated-value formula.

Existing `validate_intraday_record` and `validate_intraday_batch` rules are reused. Session warnings use Vietnam 09:00–11:30 and 13:00–15:00; missing continuous-minute buckets use 09:00–11:29 and 13:00–14:29. Lunch, cross-date boundaries and auctions do not create invented candles. Source timestamps remain unchanged, including seconds/fractions. Closing-auction bar convention is unresolved; warnings are observations, not evidence that source bars need shifting. Gaps may be no-trade intervals or omissions. No universal candle count is assumed.

| Final status | Meaning / process exit |
| --- | --- |
| PROVISIONAL | Received/mapped without blocking errors; live semantics unresolved; exit 0 |
| EMPTY | Explicit source data array empty; not a proven holiday/session; exit 0 |
| PARTIAL | Individual mapping/validation rejections or duplicate-candle batch errors; exit 1 |
| FAILED | Request, malformed response, pagination loop/truncation/bound failure; exit 1 |
| Invalid CLI / request plan | Parser/validation failure; exit 2 |

Structural warnings may accompany PROVISIONAL. Completeness is always **UNVERIFIED**, independent of HTTP success, pagination termination, validation PASS or exit 0. Validation PASS means only that mapped numeric/identity/time shape passed offline-defined rules. Invalid records are not silently repaired; duplicates remain in preview evidence and prevent a clean batch claim.

## Database contract inspection (no persistence)

Current schema: `stock_raw_intraday` has symbol/time/data_hash unique index, original nullable payload JSONB and source provenance (default SSI). It is not the monthly-partitioned clean table. `stock_intraday` has `(symbol,timeframe,time)` primary key and monthly time partitions, nullable OHLCV/value/context and additional existing columns. Preview uses neither persistence helper nor schema query, changes no partitions/rows and does not relabel historical provenance.

Historical `20260803_add_raw_intraday_payload.sql` targets `raw_intraday`; `20260826_standardize_stock_table_names.sql` renames it to `stock_raw_intraday`. This is an observed migration-history naming difference, not a reason to create/rename a table in this task. Actual deployed schema/order remains unverified. Future manual ingestion must verify deployed constraints/partitions and assess raw source/hash identity across historical sources in a separate reviewed proposal; no preview migration is needed.

## Production promotion checklist — separate task after acceptance

1. Configure SSI credentials and approved network access; capture bounded real responses for SSI and another symbol/date on completed sessions. Do not capture secrets in fixtures.
2. Verify query keys, bounds, sort, envelope/metadata and every page boundary; compare first/last candles and totals without a universal count.
3. Establish timestamp format/timezone/bar-start-or-end, source price scaling and per-candle volume units from actual responses and SSI documentation. Keep unresolved rows blocked.
4. Review raw/clean comparisons, errors, duplicates, session/gap evidence and estimated value. Obtain owner acceptance of the mapping.
5. In a separate task verify deployed raw/clean keys, source/hash provenance, payload/nullable fields and monthly partitions read-only; propose a migration only if a proven production contract change needs review.
6. Implement/review manual raw-first, validated-clean 1m persistence with idempotency and bounded scope; then separately authorize promotion of registry/CLI. Scheduling and historical backfill require their own scope and approval. This preview performs none of these steps automatically.

Migration: none. Data impact: none. Backfill: none. No features, signals, backtests or alerts are triggered.
