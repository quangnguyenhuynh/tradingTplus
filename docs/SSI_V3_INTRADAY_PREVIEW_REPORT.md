# SSI v3 Stock Intraday 1m Preview report

[Tiếng Việt](SSI_V3_INTRADAY_PREVIEW_REPORT.vi.md) · [Runbook and checklist](STOCK_INTRADAY_PIPELINE.md)

## Overall result: PARTIAL

The read-only preview, bounded pagination and shared mapping/validation are implemented and offline-tested. SSI v3 live verification is **NOT_RUN** because neither SSI_API_KEY nor SSI_API_SECRET is configured. SSI network access is also not established. No captured v3 intraday response or new authoritative intraday specification is available to resolve query/units/bar semantics. No invented market fixture is substituted for evidence. New tests explicitly use synthetic protocol/calculator inputs, not captured SSI responses.

GitHub verified base dev `804de03b819dedebcf32b1a97496d059978e1a63` (PR #179); its tree matches the existing documentation snapshot. Its commit hash was verified before creating feat/ssi-v3-intraday-preview. The pre-edit audit covered AGENTS, CLI/preflight, provider/contracts/client/adapter, ingest helpers, validators/completeness, value estimator, DB client/schema/migrations, inspector/tests/workflow/docs. No retired API or adapter fallback is used.

## Previous behavior, gaps and implementation

The preliminary ohlc_1m client concatenated a date/time string and used the generic pager that stops on short pages. The inspector mapped one page and computed value through a second mapping pass; naive timestamps were assumed to be Vietnam time without v3 evidence. Nullable OHLCV contract metadata does not replace the pipeline's required OHLCV validation. Historical v2 bar metadata is not proof of a v3 convention.

The 1m builder now normalizes dates/paging, downloads until evidenced termination or explicit failure and preserves received raw/pages on truncation/repeat/count errors. Adapter and inspector share a mapper and reuse existing value estimation/validation. Missing timestamp timezone/date is never guessed. --limit controls display; --full-json exposes every fetched page. Production registry, disabled CLI gates and workflow are unchanged.

## Endpoint, response, timestamp and units

Only candidate: GET https://api.ssi.com.vn/api/v3/data/ohlc with symbol/from/to/timeFrame=1m/pageIndex/pageSize and optional native-route ascending. Builder bounds are YYYY/MM/DD 00:00:00 through YYYY/MM/DD 23:59:59; provider acceptance/inclusivity/sort are not live-verified. Inspector defaults pageSize 10 and max-pages 100; client default pageSize 1000. Syntax/range/paging are checked before I/O.

Decoder support reflects existing repository conventions, not a verified real SSI response: top-level array or data/items/dataList/result arrays, bounded data/result/response nesting. Unknown/malformed shapes and provider failures are errors. pageIndex/pagesCount/totalRecord metadata is checked when available; itemsCount is not assumed to mean total across all pages. Raw response envelopes/candles remain intact; source value is not canonical turnover.

Only full source time with offset/Z is accepted, converted to UTC and checked against the requested Vietnam date range. Time-only/date-only/naive/epoch and other unverified forms reject; request dates never manufacture candle time. A supplied source date must agree with the timestamp. Seconds/fractions are retained. Naive timezone, bar-start/bar-end, price scaling and per-candle-volume semantics are **BLOCKED** pending real evidence. definitions.json is unchanged because historical v2 metadata cannot yet be replaced with a verified v3 convention.

## Field-by-field mapping

| Canonical | Handling |
| --- | --- |
| symbol | Request identity checked against source symbol if present |
| time | ohlc.time → intraday_timestamp; full aware timestamp required |
| timeframe | 1m; conflicting returned timeFrame rejects |
| open/high/low/close | Same-named finite positive floats, OHLC inequalities; VND scale unverified |
| volume | Exact nonnegative integral BIGINT from same-named source; units/per-candle meaning unverified; no cumulative differencing |
| value | Reuses int(round(close * volume)), estimated; source value never becomes canonical turnover |
| reference_price/ceiling_price/floor_price | NULL/unsupported until equivalent fields/context are verified; no daily DB lookup |

Missing optional values remain null in mapping evidence; missing record-validator-required OHLCV rejects the candidate. Raw data and errors remain observable. Invalid prices/volume/time are never repaired into a valid record.

Synthetic test comparison extending the repository's existing 10.5/100 input (not a real SSI payload): time=2026-09-08T09:15:00+07:00, OHLC=10.5, volume=100 → time=2026-09-08T02:15:00Z, timeframe=1m, OHLC=10.5, volume=100, value=1050, three context prices=null. Naive time=2026/09/08 09:15:00 is rejected rather than guessed.

## Pagination and quality evidence

Tests exercise two short nonempty pages followed by an explicit empty page: all three calls occur. Valid terminal metadata terminates; repeats/reordered repeats, mismatched pageIndex, changing totals, terminal count mismatch, early empty pages and page limits fail with received raw evidence. A request failure after page one retains that page's raw/candidates. Bounded retries and provider/JSON/auth/network errors are distinct from no-data. Starts after page one are explicitly suffix scope.

Tests cover identity/date/UTC, invalid timestamp, finite positive OHLC/inequalities, nonnegative integral volume, nulls, missing context, raw ordering, duplicates, morning/lunch/afternoon/auction observations, continuous-minute gaps and no cross-date/lunch stitching. No candle is fabricated and no universal count assumed. Duplicates remain visible and fail batch validation; structural warnings are separate. Completeness remains UNVERIFIED even when HTTP/paging/validation pass. A clean nonempty preview is still PROVISIONAL, not certified source readiness.

## Storage contracts — code/schema inspection only

Current raw stock_raw_intraday has symbol/time/data_hash uniqueness, nullable payload JSONB and source default SSI. Clean stock_intraday has symbol/timeframe/time primary key and monthly time partitions. The 20260803 payload migration targets raw_intraday; the 20260826 migration renames it stock_raw_intraday. This explains the observed historical names but does not certify deployed production migration order. Schema/conflict keys/source history are unchanged. Future ingestion must verify deployed keys/partitions/source/hash provenance and separately propose any proven required cross-source identity change.

Migration: **none**. Database impact: **none** (no DB reads/writes, row/table/index/partition changes). Backfill: **none**. Features/research/master/streaming and intraday schedules/production ingestion remain unchanged.

## Modified files

- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/DATA_CONVENTIONS.md`
- `docs/DATA_CONVENTIONS.vi.md`
- `docs/STOCK_INTRADAY_PIPELINE.md`
- `docs/STOCK_INTRADAY_PIPELINE.vi.md`
- `scripts/inspectors/ssi_rest/README.md`
- `scripts/inspectors/ssi_rest/README.vi.md`
- `scripts/inspectors/ssi_rest/endpoints.py`
- `scripts/inspectors/ssi_rest/inspect.py`
- `scripts/inspectors/ssi_rest/mapping.py`
- `src/contracts/mappings/ssi_v3.json`
- `src/contracts/transforms.py`
- `src/ingest/stock_intraday/README.md`
- `src/ingest/stock_intraday/README.vi.md`
- `src/providers/ssi/README.md`
- `src/providers/ssi/README.vi.md`
- `src/providers/ssi/adapters/v3.py`
- `src/providers/ssi/clients/rest_v3.py`
- `tests/inspectors/test_ssi_api_mapping.py`

## Created files

- `docs/SSI_V3_INTRADAY_PREVIEW_REPORT.md`
- `docs/SSI_V3_INTRADAY_PREVIEW_REPORT.vi.md`
- `src/contracts/intraday_preview.py`
- `src/providers/ssi/adapters/intraday_preview.py`
- `tests/data_preview/test_intraday_preview.py`

## Validation commands and results

```bash
.venv/bin/python -m pytest -q tests/inspectors tests/data_contracts tests/data_sources tests/data_preview tests/ingest tests/validation tests/cli
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall main.py src scripts tests
.venv/bin/python scripts/inspectors/ssi_rest/inspect.py list
.venv/bin/python scripts/inspectors/ssi_rest/inspect.py run --help
git diff --check
```

Final combined tests: **372 passed**; full suite: **651 passed, 7 skipped** (PostgreSQL atomic-replace tests require TEST_DATABASE_URL). There are 74 new tests; one existing test now rejects the unverified naive-time assumption. Daily/Index, feature and disabled-capability regressions pass; feature tests were not changed. Compile/help/list/whitespace and documentation links/example syntax were checked offline. A credential-free preview invocation confirms FAILED/exit 1 with a missing-credential message and no traceback/network access. No live SSI/Supabase or write smoke test was performed.

## Production-readiness decision and next step

**Do not promote to production.** Remaining risks: no real source evidence; units/time/bar/sort/bounds and metadata semantics unresolved; session coverage and deployed schema not certified. Next configure credentials and approved SSI access, inspect SSI on a completed day and a second symbol/date read-only, review raw/clean evidence and settle semantics. After owner acceptance, a separate task can implement manual raw-first/validated-clean persistence and verify idempotency/partitions/provenance before registry/CLI promotion. Scheduling/backfill remain separate scope. See the full checklist in the runbook.

Final checks after the error-body retention refinement: `.venv/bin/python -m pytest -q tests/data_preview tests/data_sources tests/inspectors tests/cli` → **217 passed**. Offline link and request-plan/parser checks: **22 inspector examples passed**. Full suite before that diagnostic-only refinement: 651 passed, 7 skipped; source/feature algorithms were not changed by the refinement.
