# SSI v3 Intraday 1m — read-only operational runbook

[Tiếng Việt](STOCK_INTRADAY_PIPELINE.vi.md) · [CLI](CLI_USAGE.md) · [Verification report](SSI_V3_INTRADAY_PREVIEW_REPORT.md)


## Guarded manual intraday pilot

`stock-intraday` now supports exactly one explicit symbol and Vietnam trading date. Default/`--dry-run` is READ-ONLY; only `--write` authorizes the guarded raw → clean insert sequence. SSI credentials are needed; Supabase service credentials enable read-only eligibility/conflict preflight and are required for writes. Without DB configuration, dry-run reports `NOT_RUN_NO_CREDENTIALS`, unknown planned counts and `write_ready=false`.

```bash
python main.py stock-intraday 20/10/2026 --symbols SSI
python main.py stock-intraday 20/10/2026 --symbols SSI --write
```

The second command is **owner-only after reviewing dry-run/preflight**. No ranges, ALL/wildcards, omitted scope, multiple symbols or future dates. Both persisted master statuses must be active. Source is only `ssi_v3`, timeframe only `1m`; canonical value is exact `ohlc.value`, with missing/invalid values blocking this pilot and no estimation fallback. Identical existing rows are skipped; differing canonical clean rows or raw key/source/payload conflicts block. No force overwrite. Raw is confirmed before clean; a partial/ambiguous write exits nonzero and requires scoped inspection then a safe rerun. Cross-table atomicity is not promised. Completeness remains UNVERIFIED. Other intraday ingest/backfill/refill/streaming commands and the schedule remain disabled. Features/signals/backtests never run from this pilot.

See [implementation report](SSI_V3_INTRADAY_MANUAL_REPORT.md) for sequence, idempotency, partition behavior, recovery and owner verification. The inspector remains entirely read-only; registry readiness remains preview, with no generic production factory.

## Scope and evidence

Owner-provided live SSI excerpts for 2026-10-20 verify `ohlc.tradingDate` in `YYYY/MM/DD HH:mm:ss`, source `ohlc.value`, and terminal `{"code":204,"msg":"No Content"}`. This exact source-local timestamp is explicitly interpreted in `Asia/Ho_Chi_Minh` and normalized to UTC; valid explicit-offset forms remain supported. The legacy `time` alias still requires an explicit timezone. Date-only/time-only and arbitrary naive formats remain rejected; no request-date fabrication or minute shifting.

Canonical v3 `value` is **SSI-reported intraday candle value**, parsed exactly as a nonnegative signed-BIGINT integer without float conversion. There is **no calculated estimate or fallback**. Absent/null/empty source value stays NULL with SOURCE_VALUE_MISSING; malformed/non-finite/fractional/negative/overflow value rejects the candidate. Zero stays zero. Source-value presence, numeric validity and preservation are reported separately from independently verified market-data semantics (still false).

The verified 204/No Content envelope terminates OHLC 1m paging only without conflicting payload/error markers and after metadata/count checks. Its original envelope is retained and termination is provider_no_content_204. Short nonempty pages never terminate by themselves; repeats, wrong totals, malformed/errors and page-limit truncation still fail. --limit controls display only; --full-json retains received raw pages, candidates and diagnostics.

The supplied day had 226 unique rows over 23 nonempty pages then page 24, descending order, 135 morning/90 afternoon/one 14:45 candle. These are owner-reported observations for that day, not a universal count or a formula rule. Only two real candle objects and the terminal envelope were supplied; offline replay verifies those 2/2 without reconstructing missing rows. Agent live rerun: NOT_RUN (no credentials). Bar-start/end, independent value/turnover semantics and market completeness remain unverified. Unattended ingestion/scheduling remains disabled; the inspector preview performs zero database reads/writes.


## Run safely

Run at repository root in the Python 3.11 virtual environment with requirements installed. Set SSI_API_KEY and SSI_API_SECRET locally; Supabase credentials are not needed. Help/list are local. No credential is stored in the sample fixture. These command examples are parser/plan checked offline; they are the owner's next read-only verification commands.

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --page-size 10 --max-pages 100 --limit 5
```

There is no new CLI command. Existing native intraday-ohlc routes use the same provider adapter/mapper. Unattended intraday-ingest, backfill-intraday, combined backfill and refill still return NOT_IMPLEMENTED before service access. Historical clean 1m may still feed independent feature jobs, which this preview never triggers.

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

Report includes actual timestamp field/interpretation, received raw and mapped/rejected counts, requested/received pages, terminal reason, raw and UTC endpoints, chronological bounds, duplicates, preserved received order, OHLCV/identity errors and structural warnings. Descending source order is retained, with a sorted clean validation view; mixed-order warnings remain visible and block the pilot. Session/gap rules reuse existing validators; lunch/auction/no-trade gaps do not create fake candles. Completeness always stays UNVERIFIED.

source_value_present_count means the API row supplied a non-null/nonempty value; source_value_numeric_valid_count means strict numeric parsing passed; source_value_mapped_count means a clean candidate actually preserved it. source_value_missing_count and source_value_invalid_count remain distinct; source_value_semantics_verified=false means official matched-turnover meaning has not been independently certified. Missing-value record warnings remain visible even outside the display sample.

PROVISIONAL (clean nonempty) and EMPTY exit 0; mapping/batch PARTIAL or request/paging FAILED exit 1; invalid CLI/plan exits 2. None implies production readiness or market completeness. --show-mapping prints source rules/evidence; --full-json includes all received raw pages and aligned candidates/errors. Raw strings/order/source values remain untouched.

## Database contracts: inspector and pilot

The inspector calls no DB path. The new manual pilot uses existing tables/keys through the dedicated insert-only boundary below. Legacy `upsert_intraday()` still estimates absent/NULL value; this pilot never calls that helper and blocks missing/null source value before writes. No historical provenance/value repair. Registry remains preview; CLI exposes only the single-symbol/day pilot. Schedules/backfill and unattended ingestion stay disabled. No migration or backfill required; Codex executed no live DB writes.

## Manual pilot persistence and recovery

The existing workflow delegates only to `src/ingest/stock_intraday/manual.py`. Generic ingest functions remain disabled. The provider registry stays preview with no intraday production factory. The pilot reuses `SSIV3Adapter.preview_intraday()` (complete date from page 1, existing bounded SSI retry/paging and 204 handling), never a parallel SSI client. Strict ascending and descending order are accepted; only the validation view of descending data is sorted, leaving raw objects/order untouched. Mixed order and duplicate canonical timestamps block writes. All candles must map with correct identity/date, valid OHLCV and nonmissing exact source value; no rejected-row filtering permits a partial write.

Eligibility reads precisely the requested `symbols` row, requiring `status=active` and `intraday_status=active`. Missing, unknown or inactive master rows block before fetch when DB is configured. No master activation or active-universe fallback. Scope validation happens before client construction. A holiday/empty response blocks writes without inventing candles. Dry-run without DB configuration validates source only, and explicitly does not certify eligibility or conflicts.

Preflight uses `symbol=SSI`, UTC `time >= 2026-10-19T17:00:00Z` and `time < 2026-10-20T17:00:00Z` for Vietnam 2026-10-20; clean queries also require `timeframe=1m`. All DB reads page in batches of 100 with exact count checking, bounded at 10,000 rows (bound/incomplete/changing counts fail closed). No UTC-calendar-day shortcut. Existing extra clean timestamps in that scope block rather than allowing a misleading count mismatch after writes. Other dates, symbols and timeframes are untouched.

Both payload layers are constructed before the first mutation. Raw uses only existing symbol/time/OHLCV/data_hash/payload/source/fetched_at fields; original source `value` remains in payload. SHA-256 hashes canonical UTF-8 JSON (sorted keys, compact separators, no fetch/transport timestamps). Audit timestamps are supplied explicitly. Raw conflict identity is `(symbol,time,data_hash)` without source: same-key differences in source, payload or raw values block. Historical raw hashes outside the current candidate keys remain untouched and are counted separately; total raw scope count may exceed matching source count.

Clean uses existing `(symbol,timeframe,time)` and OHLCV/value fields, `1m` only. Exact integer source `value` bypasses `upsert_intraday()` and its legacy estimate fallback entirely; missing/null/invalid source value blocks before either write. The general nullable contract and unrelated callers remain unchanged. Existing identical canonical clean values are skipped without relabeling unknown provenance. Any changed canonical field blocks the whole preflight. Created/fetched timestamps never affect equality/hash.

Write sequence:

1. Finish source fetch/mapping/batch validation, eligibility and both conflict checks.
2. Insert eligible raw via `ignore_duplicates=True`, then read the exact scope and compare every expected raw identity, original payload and source.
3. Recheck eligibility and clean conflicts. Create only UTC months actually needed by new clean rows using the existing `create_partition_if_not_exists` RPC; none in dry-run or a successful no-op rerun.
4. Insert eligible clean via `ignore_duplicates=True`. Concurrent conflicting rows cannot be overwritten; final readback detects differences and fails.
5. Read both exact scopes again; verify all expected raw identities and clean timestamps/count/canonical values. Report consistency PASS while completeness remains UNVERIFIED. Structural gap/session warnings are observations, not missing-data proof or a universal 226-candle requirement.

Each DB request has one application attempt (bounded); explicit reruns recover uncertain outcomes. The two tables are separate HTTP writes with no cross-table atomicity. Raw success followed by clean/partition/readback failure returns PARTIAL, nonzero exit and failed stage. Counts include acknowledged insert batches only; `insert_counts_confirmed=false` warns a failed insert request may have committed additional rows. Preserve evidence, inspect exact symbol/day and resolve conflicts before rerunning the same command. Identical raw is skipped and missing clean inserted; no cleanup/delete/overwrite occurs. Successful reruns are no-ops. Independent concurrent writers may still change rows after the final readback; stop such jobs during owner verification. This pilot never updates existing rows.

## Owner verification after merge

Codex did not execute live Supabase writes. No migration, historical repair or backfill is required. With local SSI/Supabase service configuration, the owner should run the read-only example above, review eligibility, whole-date pagination, zero rejected/duplicate/missing/invalid values, canonical timestamps, conflicts, planned counts and structural warnings. Only then run the explicit write example and repeat it. Require raw/clean readback consistency PASS and zero new rows on repeat; retain the three JSON reports. Do not interpret OK or PASS as market completeness certification. Keep all automated jobs disabled. After owner validation, multi-symbol/history remains a separate task requiring authorization.

Owner evidence supplied for SSI 2026-10-20, HPG 2026-10-20 and SSI 2026-10-21: each 226 raw/226 clean/0 rejected, descending, pagination ending with 204, no duplicates or source-value errors, validation PASS, completeness UNVERIFIED. These are owner observations, not three full response captures or agent live test results.
