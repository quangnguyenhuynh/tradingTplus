# SSI v3 guarded manual intraday pilot — implementation report

[Tiếng Việt](SSI_V3_INTRADAY_MANUAL_REPORT.vi.md) · [Owner runbook](STOCK_INTRADAY_PIPELINE.md)

## Status and audit

**COMPLETE: code and required feasible offline verification. Owner live verification remains pending.** Base `dev` was rechecked at `3598a675bc1e3105b92a773d18ce0db4baab3136` (PR #181). Before modification the CLI and workflow rejected stock-intraday; registry offered preview only. Existing overwrite helpers and legacy missing-value estimation could not satisfy this pilot safely. Schema/migrations already provide raw payload, sequence/default ID, raw unique `(symbol,time,data_hash)`, clean primary key `(symbol,timeframe,time)`, nullable BIGINT value and monthly partitions/RPC. No schema change is needed. The old AGENTS estimate rule is superseded specifically for SSI v3 by the explicit source-value requirement.

## Implemented behavior

Only existing `stock-intraday` is enabled as MANUAL_PILOT. Default/--dry-run is read-only; --write is mandatory for mutation. Scope is one explicit symbol/date (DD/MM/YYYY or YYYY-MM-DD), no future date, range, wildcard, ALL, comma or multi-symbol scope, including repeated duplicate arguments. Guarding precedes external client construction. Explicit source resolves stock_intraday rather than stock_daily, ssi_v3 only.

The registry and its daily/index/inspector consumers were audited: daily/index still require production adapters, inspectors resolve preview, and only the isolated manual route resolves intraday preview. Generic `fetch('stock_intraday')`, intraday-ingest, backfill-intraday, combined backfill, refill and streaming-ingest remain unavailable. Master commands remain disabled too. No schedule/workflow enablement or automatic features/signals/backtests.

The service reuses the verified SSI preview fetch/mapping/pagination/204 implementation. Every candle must map and validate, including exact identity/Vietnam date, OHLCV, exact nonmissing source value, whole scope from page 1, nonempty source and no duplicates/mixed order. Descending and ascending are accepted. A sorted descending validation view removes misleading unsorted warnings without changing raw evidence or silencing actual mixed anomalies. Existing general nullable value contract remains unchanged.

Eligibility requires the persisted requested symbol's status and intraday_status both active; blocked control is named and never auto-activated. With configured DB, exact symbol/local-day preflight pages with exact count checks. Example 2026-10-20: UTC [2026-10-19T17:00:00Z, 2026-10-20T17:00:00Z). No other symbol/date/timeframe is written. Dry-run without DB configuration reports unperformed eligibility/conflict checks, unknown planned counts and write_ready=false.

## Raw, clean, collision and recovery policy

Raw rows use existing symbol/time/OHLCV/data_hash/payload/source/fetched_at columns; exact original candle JSON, strings, tradingDate and value remain in payload. Source is ssi_v3. Hash is deterministic SHA-256 over canonical original JSON, excluding audit/transport time. No synthetic candle or terminal envelope is persisted. Sequence/default ID is left to the existing database.

Clean rows use existing symbol/timeframe/time/OHLCV/value/created_at fields with timeframe 1m. Source value remains the exact validated integer; the manual path never calls the legacy upsert_intraday estimator or overwrite helpers. Existing identical canonical rows are skipped and never relabeled with invented provenance. Different values or unexpected clean timestamps block the full preflight. Raw same-key differences, including cross-source collision or historical missing/different payload, also block. Unrelated historical raw hashes stay untouched; matching and total raw counts are distinct.

Both payloads, source validation and both conflict preflights complete before mutation. Eligible raw is inserted then read back before clean; eligibility and clean preflight are rechecked. Only then may the existing partition RPC create UTC months required by new clean rows. No partition in dry-run or no-op rerun. Both insert phases use on-conflict DO NOTHING (ignore_duplicates=True), protecting historical/concurrent rows from overwrite. Scoped readbacks compare every raw identity/payload/source and clean count/timestamps/canonical values. Reruns skip identical rows and safely fill missing clean after raw-only success. No destructive cleanup/force option.

Separate requests are not a cross-table transaction. Failure after any mutation attempt is PARTIAL/nonzero; earlier blocking is BLOCKED/nonzero. The failed stage and recovery are explicit. Each DB request has one application attempt; acknowledged batches are counted and failed insert outcomes marked unconfirmed. An ambiguous request can have committed rows, so inspect exact scope then rerun. Structural gap/session warnings remain observations. Completeness is always UNVERIFIED, never certified by 226 rows or HTTP success.

## Verification

```bash
.venv/bin/python -m pytest -q tests/ingest/test_manual_intraday.py
.venv/bin/python -m pytest -q tests/ingest/test_manual_intraday.py tests/cli/test_manual_intraday_cli.py
.venv/bin/python -m pytest -q tests/data_preview tests/ingest tests/pipeline tests/cli tests/validation
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall main.py src scripts tests
.venv/bin/python main.py --help
.venv/bin/python main.py stock-intraday --help
git diff --check
```

The initial manual tests passed 48; after CLI and additional edge coverage, **73 new manual/CLI tests** are included. Final applicable regression group: **489 passed**. Final full suite: **791 passed, 7 skipped**. Compile, parser/help and diff checks passed. Earlier full run before six final edge cases: 785 passed/7 skipped. All source and persistence calls in the new tests are fakes; cases include 204/multiple pages, invalid HTTP/API/truncation, bad mapping/value/volume/OHLC, duplicates/mixed/descending, default dry-run, exact UTC boundaries, both eligibility controls, paging/count truncation, raw payload/source/hash, zero and non-estimated value, cross-source/historical/concurrent conflicts, idempotency, acknowledged multi-batch failure, partial recovery and readback count/value mismatches. Workflow delegation and existing disabled-command tests preserve downstream isolation; Daily/Index/features regressions pass.

Seven existing PostgreSQL replacement-RPC tests skip because TEST_DATABASE_URL is unset. PostgreSQL/initdb/psql binaries are absent; Docker client exists but daemon socket access is denied, so disposable PostgreSQL integration was unavailable. No live SSI/Supabase smoke was run (credentials unavailable); this is pending owner verification, not a passing live test. Current Python upsert docs and installed SDK signature confirm ignore_duplicates/on_conflict/returning support: [Supabase Python reference](https://supabase.com/docs/reference/python/upsert). Changelog markdown fetch was unsupported; HTML changelog was reviewed, with no relevant change to these options.

## Database impact and remaining limits

Migration: **none**. New tables/columns/indexes/RPCs: none. Existing live data impacted: **none**. Historical repair/backfill: **none**. Features, research formulas and downstream data unchanged.

**No live Supabase writes were executed by Codex.**

Runtime still depends on deployed constraints, service permissions, compatible partition RPC/timezone settings and reachable SSI/Supabase. Missing constraints or failed RPC fail closed, never fall back to plain insert/overwrite. Raw identity lacks source; same-key source differences require owner investigation. Clean provenance is not stored and identical historical rows cannot be certified as originally SSI v3. Conflicts are reported, never automatically repaired. Other writers can alter data after readback; stop them during pilot verification. Bar start/end, independent turnover semantics and full session coverage remain unverified. No 226-row rule, missing-minute synthesis or automatic backfill. DB preflight bound is 10,000 scoped rows and source paging remains bounded by the existing client.

## Owner verification and next step

After merge, with local credentials and both master statuses already active, run:

```bash
python main.py stock-intraday 20/10/2026 --symbols SSI
# Owner only, after reviewing dry-run and conflict/eligibility preflight:
python main.py stock-intraday 20/10/2026 --symbols SSI --write
# Owner repeats the same --write command to confirm no new rows.
```

Retain JSON from dry-run/write/repeat. Require source validation and whole-date pagination, no rejects/duplicates/value errors/conflicts, raw/clean readback PASS and zero inserted counts on repeat. Preserve UNVERIFIED completeness. If PARTIAL, inspect exact scope and conflicts then rerun; never delete historical data to make it pass. Next step is owner verification of this single pilot, before any separately authorized multi-symbol/backfill work.

## Modified files

- `README.md`
- `README.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/CURRENT_STATE.md`
- `docs/SSI_V3_INTRADAY_PREVIEW_REPORT.md`
- `docs/SSI_V3_INTRADAY_PREVIEW_REPORT.vi.md`
- `docs/STOCK_INTRADAY_PIPELINE.md`
- `docs/STOCK_INTRADAY_PIPELINE.vi.md`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/cli/__init__.py`
- `src/cli/parser.py`
- `src/cli/stock.py`
- `src/ingest/stock_intraday/README.md`
- `src/ingest/stock_intraday/README.vi.md`
- `src/ingest/workflows/README.md`
- `src/ingest/workflows/README.vi.md`
- `src/ingest/workflows/stock_intraday.py`
- `src/providers/ssi/README.md`
- `src/providers/ssi/README.vi.md`
- `src/providers/ssi/adapters/intraday_preview.py`
- `tests/cli/test_capability_retirement.py`
- `tests/pipeline/test_stock_intraday_pipeline.py`

## Created files

- `src/ingest/stock_intraday/manual.py`
- `tests/cli/test_manual_intraday_cli.py`
- `tests/ingest/test_manual_intraday.py`
- `docs/SSI_V3_INTRADAY_MANUAL_REPORT.md`
- `docs/SSI_V3_INTRADAY_MANUAL_REPORT.vi.md`
