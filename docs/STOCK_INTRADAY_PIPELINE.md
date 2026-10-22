# SSI v3 Intraday 1m — read-only operational runbook

[Tiếng Việt](STOCK_INTRADAY_PIPELINE.vi.md) · [CLI](CLI_USAGE.md) · [Verification report](SSI_V3_INTRADAY_PREVIEW_REPORT.md)

## Scope and evidence

Owner-provided live SSI excerpts for 2026-10-20 verify `ohlc.tradingDate` in `YYYY/MM/DD HH:mm:ss`, source `ohlc.value`, and terminal `{"code":204,"msg":"No Content"}`. This exact source-local timestamp is explicitly interpreted in `Asia/Ho_Chi_Minh` and normalized to UTC; valid explicit-offset forms remain supported. The legacy `time` alias still requires an explicit timezone. Date-only/time-only and arbitrary naive formats remain rejected; no request-date fabrication or minute shifting.

Canonical v3 `value` is **SSI-reported intraday candle value**, parsed exactly as a nonnegative signed-BIGINT integer without float conversion. There is **no calculated estimate or fallback**. Absent/null/empty source value stays NULL with SOURCE_VALUE_MISSING; malformed/non-finite/fractional/negative/overflow value rejects the candidate. Zero stays zero. Source-value presence, numeric validity and preservation are reported separately from independently verified market-data semantics (still false).

The verified 204/No Content envelope terminates OHLC 1m paging only without conflicting payload/error markers and after metadata/count checks. Its original envelope is retained and termination is provider_no_content_204. Short nonempty pages never terminate by themselves; repeats, wrong totals, malformed/errors and page-limit truncation still fail. --limit controls display only; --full-json retains received raw pages, candidates and diagnostics.

The supplied day had 226 unique rows over 23 nonempty pages then page 24, descending order, 135 morning/90 afternoon/one 14:45 candle. These are owner-reported observations for that day, not a universal count or a formula rule. Only two real candle objects and the terminal envelope were supplied; offline replay verifies those 2/2 without reconstructing missing rows. Agent live rerun: NOT_RUN (no credentials). Bar-start/end, independent value/turnover semantics and market completeness remain unverified. Production ingestion/scheduling remains disabled; preview performs zero database reads/writes.


## Run safely

Run at repository root in the Python 3.11 virtual environment with requirements installed. Set SSI_API_KEY and SSI_API_SECRET locally; Supabase credentials are not needed. Help/list are local. No credential is stored in the sample fixture. These command examples are parser/plan checked offline; they are the owner's next read-only verification commands.

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --page-size 10 --max-pages 100 --limit 5
```

There is no new CLI command. Existing native intraday-ohlc routes use the same provider adapter/mapper. Production intraday-ingest, stock-intraday, backfill-intraday, combined backfill and refill still return NOT_IMPLEMENTED before service access. Historical clean 1m may still feed independent feature jobs, which this preview never triggers.

## Request and pagination

GET https://api.ssi.com.vn/api/v3/data/ohlc with symbol, from/to (YYYY/MM/DD 00:00:00 through 23:59:59), timeFrame=1m, pageIndex/pageSize. Inspector defaults page index 1, size 10, max-pages 100; client default size 1000. Positive paging and inclusive ordered day bounds are constructed before I/O. Native --ascending remains optional; no sorting is imposed on raw data. Sort support, date-bound inclusivity and metadata meanings beyond supplied evidence need independent confirmation.

Fetch successive pages until explicit empty array, consistent declared pagesCount, or verified 204/No Content. No Content on the first page means EMPTY, without candles. A malformed or conflicting 204 is FAILED; it is never a generic exemption for HTTP/API errors. Wrong page identity, changing totals/page counts, early empty terminal pages, repeated/reordered pages, mismatched final totalRecord and max-pages all fail with received evidence retained. Terminal metadata is checked against prior pages too. Requests starting after page 1 are labeled suffix scope. No candle count is hardcoded. HTTP retry bounds remain separate from logical page/request counts.

204 recognition is limited to the v3 OHLC 1m path. Daily/Index client error behavior is unchanged. Raw pages include the terminal envelope. The recognized terminal has code 204 (integer or string), a No Content message, no nonempty/unsupported payload and no contradictory status/error markers. Missing message, nonempty data, other errors or malformed metadata reject.

## Canonical mapping

Dictionary: src/contracts/mappings/ssi_v3.json, mapping 1.2.0-preview, unchanged contract version 1.0.0. The provider adapter and inspector share src/contracts/intraday_preview.py; the generic engine passes source-field context to transforms so market-local parsing cannot leak to the legacy time alias or other datasets.

| Field | Mapping and validation |
| --- | --- |
| symbol | Request identity checked against returned symbol |
| time | ohlc.tradingDate → source-specific transform → aware UTC; slash local format uses Vietnam timezone; explicit ISO offset retains its instant |
| timeframe | Constant 1m; conflicting source timeframe rejects |
| open/high/low/close | Same-named finite positive numbers, unchanged OHLC inequalities; original strings remain raw |
| volume | Same-named exact nonnegative integer in BIGINT range, no cumulative differencing |
| value | ohlc.value → exact Decimal/integer parsing → Python int; never close × volume |
| reference_price/ceiling_price/floor_price | NULL while source/context fields remain unconfirmed; no DB lookup |

Value parsing accepts exact integer or decimal-string representations with integral numeric content (including integral decimal/scientific strings), but rejects float/bool input to avoid already-rounded large numbers. It rejects non-finite, negative, fractional and out-of-range values. Null/missing/empty is nullable and warned, never converted to zero or an estimate. Valid value remains unchanged even when it differs from close × volume.

The copied 14:45 candle maps tradingDate 2026/10/20 14:45:00 → 2026-10-20T07:45:00Z, close 19950, volume 2626600, value 52400670000. The copied 14:29 candle maps to 07:29:00Z with value 2560650000. A synthetic close=19950, volume=100, value=1994000 case explicitly proves that value is not replaced by 1995000. The synthetic mismatch is not real market evidence.

Seconds and supported microseconds are preserved. Missing/invalid date, out-of-request Vietnam date, inconsistent source identity, time-only/date-only/epoch and unsupported naive formats reject. A full aware tradingDate is checked by its Vietnam instant, not by truncating its written UTC date. Bar-start versus bar-end remains unverified; no fabricated 14:30–14:44 candles, no minute shifts and no cross-session/date joins.

## Report and quality

Report includes actual timestamp field/interpretation, received raw and mapped/rejected counts, requested/received pages, terminal reason, raw and UTC endpoints, chronological bounds, duplicates, preserved received order, OHLCV/identity errors and structural warnings. Descending source order is retained; ascending-view inversion warnings are not alone proof of corrupted data. Session/gap rules reuse existing validators; lunch/auction/no-trade gaps do not create fake candles. Completeness always stays UNVERIFIED.

source_value_present_count means the API row supplied a non-null/nonempty value; source_value_numeric_valid_count means strict numeric parsing passed; source_value_mapped_count means a clean candidate actually preserved it. source_value_missing_count and source_value_invalid_count remain distinct; source_value_semantics_verified=false means official matched-turnover meaning has not been independently certified. Missing-value record warnings remain visible even outside the display sample.

PROVISIONAL (clean nonempty) and EMPTY exit 0; mapping/batch PARTIAL or request/paging FAILED exit 1; invalid CLI/plan exits 2. None implies production readiness or market completeness. --show-mapping prints source rules/evidence; --full-json includes all received raw pages and aligned candidates/errors. Raw strings/order/source values remain untouched.

## Database contracts and future persistence guard

No DB path is called. Existing stock_raw_intraday keeps symbol/time/data_hash identity, source and nullable original payload; stock_intraday keeps symbol/timeframe/time key, nullable BIGINT value and monthly time partitions. The old payload migration names raw_intraday; the subsequent standardization migration renames it stock_raw_intraday. No rename/key/schema change is required here.

src/database/client.py:upsert_intraday still calls calculate_trade_value when value is absent/NULL. This legacy behavior and its consumers are unchanged. **Before any v3 production promotion, a source-specific persistence guard must carry reported value unchanged, preserve NULL without fallback, reject invalid source values, and prove no estimator path is invoked.** Do not simply pass NULL to the current persistence helper: it would estimate it. Any rewrite of historical estimates needs separate explicit symbol/date/provenance scope and approval; none occurs here.

Promotion next requires owner review of a new live read-only run, full raw/clean/value evidence and duplicate/page checks, independent bar/value-semantic clarification where needed, deployed constraints/partitions/provenance verification, and a separate manually scoped persistence implementation with the value guard. Registry/CLI/schedules/backfill are not enabled by this task.

Migration: none. Database writes/history modifications: none. Backfill: none. No features/signals/backtests/alerts.
