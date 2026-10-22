# SSI v3 Intraday timestamp, terminal 204 and source-value fix report

[Tiếng Việt](SSI_V3_INTRADAY_PREVIEW_REPORT.vi.md) · [Runbook](STOCK_INTRADAY_PIPELINE.md)

## Status: COMPLETE for the read-only fixes and offline verification

All three issues are fixed, the two owner-provided real candles/terminal envelope replay correctly, and offline tests ran. Agent live rerun: **NOT_RUN** because SSI credentials are unavailable. The complete 226-row capture was not supplied, so this report does not claim an independently replayed 226/226 result. Production readiness remains **false**; ingest/scheduling/backfill are disabled. Bar-start/end and official matched-turnover semantics remain independently unverified.

Base dev: 09f0ea4a1d2f5d920f3f7eb2be4eb1d7a9375831 (merged PR #180); fix branch: fix/ssi-v3-intraday-evidence. The pre-edit audit covered AGENTS, CLI, client/adapter/mapper/transforms/dictionary/engine, contract/schema/migrations, validators, estimator, DB fallback, inspector, tests and docs. The owner's new requirement explicitly supersedes the estimate convention for this v3 preview only; legacy behavior/historical provenance are not changed.

## Root causes and before/after

| Issue | Before | After |
| --- | --- | --- |
| Timestamp | ohlc.time misses real tradingDate; naive timestamps reject | ohlc.tradingDate uses explicit Asia/Ho_Chi_Minh interpretation for observed YYYY/MM/DD HH:mm:ss, then UTC |
| 204 | Client rejects API code 204 and decoder requires an array | OHLC 1m alone passes 204 for strict No Content decoding and existing consistency checks |
| Value | derived plus calculate_trade_value(close, volume) | ohlc.value parsed exactly through Decimal/integer; no estimator or fallback |

Mapping version is 1.2.0-preview; contract version 1.0.0 and fields/schema/nullability/keys remain intact. definitions.json only clarifies source/historical semantics; types/required/nullable flags do not change. The generic engine adds actual source-field context so the v3-specific transform scopes naive market-local handling to tradingDate; legacy time still requires an offset. The generic aware-only transform is not broadened for other datasets.

## Evidence and raw-to-clean comparison

The fixture tests/fixtures/data_preview/ssi_v3_intraday_ssi_2026-10-20_owner_samples.json copies exactly the two real candle objects and terminal envelope from the owner request, with no credentials/full logs. Array/page wrappers and modified edge cases are explicitly synthetic. No missing 224 rows are reconstructed as real evidence.

| Raw tradingDate | Canonical UTC | Raw close | Raw volume | Raw value → clean int |
| --- | --- | --- | --- | --- |
| 2026/10/20 14:45:00 | 2026-10-20T07:45:00Z | 19950 | 2626600 | 52400670000 → 52400670000 |
| 2026/10/20 14:29:00 | 2026-10-20T07:29:00Z | 19850 | 129000 | 2560650000 → 2560650000 |

Offline replay: raw 2, mapped 2, rejected 0, duplicates 0; raw/string representations and descending order remain unchanged. Two synthetic one-candle page wrappers followed by the real 204 envelope yield three requested/received pages, pagination_complete=true and provider_no_content_204 termination. Short pages do not stop early. No auction candles/minute shifts are introduced. Local fractional seconds up to microseconds and previously supported explicit ISO offsets retain their exact instant. Invalid/missing/out-of-range date or mismatched identity still reject.

The owner reported, for SSI 2026-10-20 only: 226 raw/unique, 23 nonempty pages, terminal 24, 135 morning + 90 afternoon + one 14:45 candle, all values present and coincidentally equal to close × volume. These remain **owner-reported observations**, not the agent's full-capture replay result or a universal completeness invariant. Equality is not permission to recalculate canonical value.

## Value preservation, nulls and failures

Canonical value is **SSI-reported intraday candle value**, not independently certified official matched turnover. No scaling/unit conversion is invented. Exact integers/integral decimal strings are parsed with Decimal, never float, preserving values above 2^53 through 2^63−1. Float/bool, non-finite, fractional, negative, overflow and malformed strings reject while raw remains intact. Zero stays zero. Missing/NULL/empty retains canonical NULL and SOURCE_VALUE_MISSING warnings, without estimate/zero substitution.

A **synthetic** close=19950, volume=100, value=1994000 test proves clean.value=1994000 rather than 1995000. The estimator is monkeypatched to fail if preview calls it. This is not a real market candle.

Report counters distinguish source_value_present_count, source_value_numeric_valid_count, source_value_mapped_count, missing/invalid counts and source_value_semantics_verified=false. Receiving a value, preserving it, validating its numeric form and independently validating market semantics are separate outcomes. Missing-value warnings remain visible outside display samples.

## Terminal 204 and retained failures

Accept integer/string code 204 with No Content and no nonempty/unsupported payload or contradictory error marker. First-page 204 means EMPTY; after data pages it terminates. Original envelope and requested/received page counts remain available. Prior pageIndex/totalRecord/pagesCount, final row counts, changed metadata, repeated/reordered pages, duplicates, short-page continuation and max-pages remain checked. Conflicting/malformed 204 and unrelated 400/401/403/500/provider failures do not become no-data. Daily/Index behavior does not inherit the OHLC 1m 204 exemption.

Completeness stays UNVERIFIED independently of pagination_complete. Descending order is preserved/reported; ascending-view/session/gap warnings never authorize data repair or candle fabrication. Missing source value respects nullability; invalid value rejects the affected candidate.

## Deferred persistence risk

src/database/client.py:upsert_intraday still calls calculate_trade_value for absent/NULL value. That method and its consumers are unchanged. Preview never invokes it and tests block DB access. Before production promotion, a source-specific v3 guard must carry value unchanged, preserve NULL without fallback, reject invalid values and prove no recomputation. Passing NULL to the existing helper is insufficient. Do not globally remove legacy fallback without auditing callers. Historical estimates require a separate explicitly authorized symbol/date/provenance repair task.

Schema remains stock_raw_intraday (symbol/time/data_hash, original payload/source) and stock_intraday (symbol/timeframe/time, monthly partitions, nullable BIGINT value). The old payload migration uses raw_intraday, renamed by the later standardization migration; no schema/key change is needed for preview.

Migration: **none**. Production DB writes/data/history changes: **none**. Backfill: **none**. No feature/signal/backtest, scheduled ingest or production capability enablement.

## Modified files

- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/DATA_CONVENTIONS.md`
- `docs/DATA_CONVENTIONS.vi.md`
- `docs/SSI_V3_INTRADAY_PREVIEW_REPORT.md`
- `docs/SSI_V3_INTRADAY_PREVIEW_REPORT.vi.md`
- `docs/STOCK_INTRADAY_PIPELINE.md`
- `docs/STOCK_INTRADAY_PIPELINE.vi.md`
- `scripts/inspectors/ssi_rest/README.md`
- `scripts/inspectors/ssi_rest/README.vi.md`
- `scripts/inspectors/ssi_rest/inspect.py`
- `src/contracts/README.md`
- `src/contracts/README.vi.md`
- `src/contracts/definitions.json`
- `src/contracts/engine.py`
- `src/contracts/intraday_preview.py`
- `src/contracts/mappings/ssi_v3.json`
- `src/contracts/transforms.py`
- `src/ingest/stock_intraday/README.md`
- `src/ingest/stock_intraday/README.vi.md`
- `src/intraday_value.py`
- `src/providers/ssi/README.md`
- `src/providers/ssi/README.vi.md`
- `src/providers/ssi/adapters/intraday_preview.py`
- `src/providers/ssi/clients/rest_v3.py`
- `tests/data_preview/test_intraday_preview.py`

## Created files

- `tests/data_preview/test_intraday_evidence_fix.py`
- `tests/fixtures/data_preview/ssi_v3_intraday_ssi_2026-10-20_owner_samples.json`

## Executed validation commands and results

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q tests/data_preview` | 148 passed |
| `.venv/bin/python -m pytest -q tests/inspectors` | 64 passed |
| `.venv/bin/python -m pytest -q tests/data_contracts` | 17 passed |
| `.venv/bin/python -m pytest -q tests/validation` | 57 passed |
| `.venv/bin/python -m pytest -q tests/ingest` | 81 passed |
| `.venv/bin/python -m pytest -q tests/cli` | 58 passed |
| `.venv/bin/python -m pytest -q` | 718 passed, 7 skipped |
| `.venv/bin/python -m compileall main.py src scripts tests` | PASS |
| `git diff --check` | PASS |

Seven PostgreSQL atomic-replace tests skip without TEST_DATABASE_URL. The full suite covers Daily/Index, feature and disabled-capability regressions; feature tests and Daily/Index logic are unchanged. Tests verify that 204 does not extend to Daily/Index, block DB access and prove no estimator call. The real fixture contains only supplied excerpts; 67 added cases accompany affected old test updates. No database write smoke test or fabricated live PASS was performed.

## Owner read-only verification commands

```bash
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --full-json
```

A separate manual-ingestion task can be considered after owner review of the full raw/clean rerun, the persistence no-recomputation/NULL guard and deployed schema/provenance/partition checks. Manual production is not enabled here; registry/CLI/workflow remain unchanged. Next run the commands above with local credentials, review terminal 204 and source-value counters, then obtain owner acceptance for a separately scoped promotion task.

Final documentation checks: 25 inspector examples pass parser/request-plan validation and changed local links resolve. Automated scope checks confirm only descriptive contract metadata changed and DB client/schema/registry/CLI gates/workflow/feature tests remain untouched.
