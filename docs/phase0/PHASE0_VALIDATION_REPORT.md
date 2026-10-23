# Phase 0 validation report

Historical closure follows. The current SSI v3 maintenance/verification report is the dated 2026-10-23 section below; the old Next step is historical, not a new instruction.

**Decision: COMPLETE_WITH_NOTES**
**Closure date:** 2026-08-03
**Scope:** data infrastructure, data validation, and deterministic feature validation only.

## Closure gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Production schema | `PASS_WITH_MANUAL_APPLY_NOTE` | `20260802_atomic_replace_features.sql` and `20260803_add_raw_intraday_payload.sql` were applied manually through Supabase SQL Editor. Production was verified read-only to have nullable/no-default `stock_raw_intraday.payload jsonb`, the secured atomic RPC, its role grants/revocations, safe empty `search_path`, and the required feature unique index. Supabase CLI migration history may not contain these records; matching deployed schema is accepted for Phase 0. Do not rerun or repair these migrations merely to change CLI history. |
| New intraday payload lineage | `PASS` | The project owner verified a new intraday ingest row with non-NULL `stock_raw_intraday.payload`. Historical NULL payloads remain valid by design and require no backfill. |
| SSI → raw → clean → feature sample | `PASS` | The owner selected production symbols, dates, and daily/intraday feature timeframes and reconciled source, raw, clean, and feature fields. Matched fields included raw payload identity/mapping plus OHLCV/value at clean and feature layers; no unexplained critical mismatch remained. Exact sample identifiers were not retained in this repository report, so future runs must record command output and scope. |
| Offline regression suite | `PASS` | Pagination, mapping, completeness, feature parity, atomic replacement, and Phase 0 validation behavior are covered by deterministic tests. |
| Calendar/completeness | `PASS_WITH_NOTES` | Completeness is evaluated per symbol, Vietnam trading date, source, timeframe, and observed sessions. Reports include counts, first/last timestamps, duplicates, and gap classification. There is no universal 226-candle rule. |

## Repeatable read-only validation

```bash
PHASE0_DATABASE_URL='postgresql://...' python scripts/checks/phase0_validate_schema.py
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-08-03 --timeframe 1d
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-08-03 --timeframe 15m --timestamp 2026-08-03T02:00:00Z
```

The schema command forces PostgreSQL `default_transaction_read_only=on`. The reconciliation command issues bounded SELECTs only. Outcomes are `PASS`, `FAIL`, or `UNKNOWN`; missing evidence never becomes a false pass. Payload inspection checks at most 100 selected rows, accepts historical NULLs, and returns `UNKNOWN` if it cannot find a non-NULL sample. Numeric comparisons default to absolute/relative tolerance `1e-6`.

## Calendar and completeness assumptions

- Interpret sessions and user-facing dates in `Asia/Ho_Chi_Minh`; retain timezone-aware UTC storage.
- A weekday is not proof of a trading day. Empty, holiday, halted, shortened-session, and source-failure cases must remain distinguishable where evidence permits.
- Do not fabricate holiday rows, forward-fill candles, or convert missing market values to zero.
- The repository still has no authoritative, versioned exchange calendar/status source. Until one is approved, official weekday holidays and exceptional sessions may remain `UNKNOWN` or warnings rather than false completeness failures.
- Candle counts vary with auctions, liquidity, halts, shortened sessions, timestamp conventions, and SSI behavior; 226 is not a universal expected count.

## Data and migration impact

This closure work applies no migration and performs no production write, ingest, RPC replacement, deletion, feature rebuild, or backfill. Historical `stock_raw_intraday.payload` stays NULL where it was not captured. No feature formula changed, so no feature backfill is required.

## Remaining risks

1. Manual SQL Editor deployment is not represented reliably in Supabase CLI migration history; deployed schema, not history alone, must be checked before later deployment operations.
2. Future evidence should retain the exact production sample symbols, dates, timeframes, timestamps, and command output; the owner validation supplied for closure did not include those identifiers in the repository.
3. No approved authoritative/versioned exchange calendar and exceptional-session status source is implemented.
4. Live SSI and Supabase checks require external credentials; an offline run must report `UNKNOWN`, not claim live verification.

## Next step

Begin Phase 1 specification for shared strategy rules and point-in-time backtesting.

## 2026-10-23 — SSI v3 diagnostics maintenance report

**Status: COMPLETE for implementation, offline regression and live read-only catalog verification. Persisted SSI v3 lineage verification remains pending on a populated owner-selected scope.** Base dev rechecked at `278da438138b50e6820b2888f17d52aa2927c96a` (PR #182). This targeted maintenance adds no quality subsystem, source integration or CLI command.

Original defects: obsolete raw_intraday/features schema references, name/text-only unique-index detection, treating PUBLIC as a named role in has_function_privilege, missing 1m support and intraday mapper branch, arbitrary limit(1) evidence, manual aggregation with NULL-to-zero, float comparison of BIGINTs, missing evidence masking verified mismatches, and unconditional completeness exit 0.

Changes: schema verifier now checks stock_raw_intraday.payload JSONB/nullable/no-default and stock_features key metadata using pg_index validity/readiness/uniqueness/full plain keys, accepting PK/constraint indexes without name dependence. Expected replace_features_atomic signature, SECURITY DEFINER, empty search_path, service_role grant and anon/authenticated/PUBLIC restrictions remain enforced. PUBLIC is inspected through ACL grantee 0, not a fictitious role. Every check retains expected/observed/status/reason and read_only=true; no RPC invocation or automatic repair.

Reconciliation supports 1m/1d/15m/60m with bounded exact-count paginated symbol/Vietnam-day SELECTs. Existing report fields remain, with per-layer results, detailed comparisons, selection and diagnostic codes added. 1m uses the real pure SSI v3 mapper over persisted payloads and never queries/requires stock_features. Timestamp equivalence uses aware UTC instants preserving seconds; volume/value use exact integer comparison, no float/tolerance, estimate or zero fill. OHLC retains explicit absolute/relative tolerance 1e-6. Missing source value remains NULL: NULL/NULL can verify preservation, while NULL/zero is a contradiction.

Only source ssi_v3 is mapped; legacy SSI/unknown source, NULL/incompatible payload and raw collisions stay UNKNOWN. Exact --timestamp never substitutes nearby rows. Otherwise 1m selects earliest v3 raw instant (or earliest raw when none is v3), examining all raw candidates at that instant. Higher timeframes choose latest persisted feature bucket and reconcile observed raw/clean constituents. Duplicate canonical identities fail. Multiple raw versions/sources return UNKNOWN rather than choosing an unrelated record.

Daily flow remains stock_raw_daily → stock_daily → stock_features(1d) with the actual daily mapper and no legacy reinterpretation. Higher intraday clean → feature OHLCV/value uses the existing pure aggregation and closed-bucket helpers, respecting their VN date/session and left-label rules; no indicators are computed or features persisted. No fixed emitted-bar count. Open/partial buckets or NULL inputs return UNKNOWN before reaching the legacy estimate helper; invalid clean prices and actual feature mismatches fail. Layers report independently, and any verified FAIL outranks missing evidence elsewhere. Coverage remains UNVERIFIED even when observed aggregate equality passes.

Completeness still calls the existing check_ingest algorithm and preserves its status/full JSON. Exit 0=OK, 1=PARTIAL/FAILED or query error, 2=invalid input/indeterminate status. Progress is redirected to stderr for parseable JSON stdout; exceptions are sanitized, nonzero and visible by type/status. Thresholds and source-coverage semantics are unchanged. Reconciliation exit 0=PASS/WARNING, 1=FAIL, 2=UNKNOWN; informational payload presence does not gate daily/selected-lineage status. Manual pilot guards/readiness and all disabled ingest/backfill/streaming paths remain unchanged.

### Verification and limits

```bash
.venv/bin/python -m pytest -q tests/validation/test_phase0.py
.venv/bin/python -m pytest -q tests/validation/test_intraday_validator.py
.venv/bin/python -m pytest -q tests/ingest/test_ingest_check.py
.venv/bin/python -m pytest -q tests/ingest/test_manual_intraday.py
.venv/bin/python -m pytest -q tests/cli/test_phase0_checks.py
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall main.py src scripts tests
.venv/bin/python scripts/checks/phase0_validate_schema.py --help
.venv/bin/python scripts/checks/phase0_reconcile_sample.py --help
.venv/bin/python scripts/checks/check_ingest.py --help
git diff --check
```

Baseline targeted tests: 105 passed. Final individual suites: Phase 0 **78 passed**, intraday validator **30 passed**, ingest completeness **15 passed**, manual pilot **54 passed**, diagnostic CLI **40 passed**. Final full suite **903 passed, 7 skipped**; compile/help/diff checks passed. Earlier full suite before ten final edge cases: 893 passed/7 skipped. Offline tests cover canonical metadata, invalid unique keys/RPC security, exact large integers and one-unit differences, source/provenance ambiguity, explicit instants/seconds, paging/bounds, NULL/zero, existing daily behavior, 15m/60m/lunch/day/bucket boundaries, partial buckets, mismatches, read-only guards and CLI statuses/JSON. Fixtures are synthetic test data, not new live SSI captures.

Through the connected Supabase tool on TradingTPus_DS, ran only SELECTs: the exact three catalog queries extracted from verify_schema confirmed nullable/no-default JSONB payload, restricted RPC security, and both valid stock_features_pkey and stock_features_symbol_timeframe_time_key. The ordinary nonunique index was correctly excluded. Live catalog answers were evaluated by verify_schema and returned PASS. No replacement RPC was executed. A bounded raw/clean SQL probe for SSI, Vietnam date 2026-10-21 (UTC [2026-10-20T17:00Z,2026-10-21T17:00Z)) returned no raw rows; a source-count SELECT in that exact scope also returned none. No live lineage PASS is claimed for the empty scope and no data was ingested to change that outcome.

Seven existing PostgreSQL replacement-RPC integration tests require TEST_DATABASE_URL and remain skipped; PostgreSQL binaries/disposable test DB are unavailable. Local diagnostic CLI end-to-end DB credentials were not configured; connector catalog SELECT verification is distinguished from a native CLI integration run. No live SSI API requests were made. Supabase current docs/changelog were consulted; markdown changelog was unsupported and HTML was used. The pending owner read-only procedure is in [checks runbook](../../scripts/checks/README.md).

### Database impact, UNKNOWN cases and next task

Migration: **none**. Schema/constraints/RPC changes: **none**. Database data impacted: **none** (SELECT only). Backfill: **not required/none**. No ingest, feature calculation, signal, backtest or alert execution. Existing formulas/persisted outputs remain unchanged.

**No live database writes were executed.**

Remaining UNKNOWN cases: absent raw/clean/feature evidence, legacy/unknown source, incompatible or NULL payload, multiple raw versions/sources, partial/open feature bucket, NULL aggregate input, bounded/capped/changing DB reads and unavailable query access. A clean→feature equality only compares stored OHLCV/value of observed clean constituents, not technical indicators or official session/source completeness. Historical timestamps/value provenance are never repaired/reinterpreted. Independent concurrent writers may change evidence after SELECT; retain scope/output and prefer a quiet verification window.

Owner commands, all read-only:

```bash
python scripts/checks/phase0_validate_schema.py
python scripts/checks/check_ingest.py --date 21/10/2026 --symbols SSI
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 1d
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 1m
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 15m
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 60m
```

Use an existing populated symbol/day to obtain actual lineage evidence; empty scopes must remain UNKNOWN. Next step: owner validates these diagnostics and retains exact JSON/timestamps. Only a subsequent separately authorized task may evaluate controlled intraday incremental/backfill. No strategy, feature formula, signal/backtest or alert change is included.

### Files modified

- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/DATA_CONVENTIONS.md`
- `docs/DATA_CONVENTIONS.vi.md`
- `docs/phase0/PHASE0_VALIDATION_REPORT.md`
- `docs/phase0/PHASE0_VALIDATION_REPORT.vi.md`
- `scripts/checks/README.md`
- `scripts/checks/README.vi.md`
- `scripts/checks/check_ingest.py`
- `scripts/checks/phase0_reconcile_sample.py`
- `src/quality/README.md`
- `src/quality/README.vi.md`
- `src/quality/validators/README.md`
- `src/quality/validators/README.vi.md`
- `src/quality/validators/phase0.py`
- `tests/validation/test_phase0.py`

### Files created

- `tests/cli/test_phase0_checks.py`
