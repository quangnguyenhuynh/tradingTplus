# Phase 0 validation report

**Decision: COMPLETE_WITH_NOTES**
**Closure date:** 2026-08-03
**Scope:** data infrastructure, data validation, and deterministic feature validation only.

## Closure gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Production schema | `PASS_WITH_MANUAL_APPLY_NOTE` | `20260802_atomic_replace_features.sql` and `20260803_add_raw_intraday_payload.sql` were applied manually through Supabase SQL Editor. Production was verified read-only to have nullable/no-default `raw_intraday.payload jsonb`, the secured atomic RPC, its role grants/revocations, safe empty `search_path`, and the required feature unique index. Supabase CLI migration history may not contain these records; matching deployed schema is accepted for Phase 0. Do not rerun or repair these migrations merely to change CLI history. |
| New intraday payload lineage | `PASS` | The project owner verified a new intraday ingest row with non-NULL `raw_intraday.payload`. Historical NULL payloads remain valid by design and require no backfill. |
| SSI → raw → clean → feature sample | `PASS` | The owner selected production symbols, dates, and daily/intraday feature timeframes and reconciled source, raw, clean, and feature fields. Matched fields included raw payload identity/mapping plus OHLCV/value at clean and feature layers; no unexplained critical mismatch remained. Exact sample identifiers were not retained in this repository report, so future runs must record command output and scope. |
| Offline regression suite | `PASS` | Pagination, mapping, completeness, feature parity, atomic replacement, and Phase 0 validation behavior are covered by deterministic tests. |
| Calendar/completeness | `PASS_WITH_NOTES` | Completeness is evaluated per symbol, Vietnam trading date, source, timeframe, and observed sessions. Reports include counts, first/last timestamps, duplicates, and gap classification. There is no universal 226-candle rule. |

## Repeatable read-only validation

```bash
PHASE0_DATABASE_URL='postgresql://...' python scripts/phase0_validate_schema.py
python scripts/phase0_reconcile_sample.py --symbol SSI --date 2026-08-03 --timeframe 1d
python scripts/phase0_reconcile_sample.py --symbol SSI --date 2026-08-03 --timeframe 15m --timestamp 2026-08-03T02:00:00Z
```

The schema command forces PostgreSQL `default_transaction_read_only=on`. The reconciliation command issues bounded SELECTs only. Outcomes are `PASS`, `FAIL`, or `UNKNOWN`; missing evidence never becomes a false pass. Payload inspection checks at most 100 selected rows, accepts historical NULLs, and returns `UNKNOWN` if it cannot find a non-NULL sample. Numeric comparisons default to absolute/relative tolerance `1e-6`.

## Calendar and completeness assumptions

- Interpret sessions and user-facing dates in `Asia/Ho_Chi_Minh`; retain timezone-aware UTC storage.
- A weekday is not proof of a trading day. Empty, holiday, halted, shortened-session, and source-failure cases must remain distinguishable where evidence permits.
- Do not fabricate holiday rows, forward-fill candles, or convert missing market values to zero.
- The repository still has no authoritative, versioned exchange calendar/status source. Until one is approved, official weekday holidays and exceptional sessions may remain `UNKNOWN` or warnings rather than false completeness failures.
- Candle counts vary with auctions, liquidity, halts, shortened sessions, timestamp conventions, and SSI behavior; 226 is not a universal expected count.

## Data and migration impact

This closure work applies no migration and performs no production write, ingest, RPC replacement, deletion, feature rebuild, or backfill. Historical `raw_intraday.payload` stays NULL where it was not captured. No feature formula changed, so no feature backfill is required.

## Remaining risks

1. Manual SQL Editor deployment is not represented reliably in Supabase CLI migration history; deployed schema, not history alone, must be checked before later deployment operations.
2. Future evidence should retain the exact production sample symbols, dates, timeframes, timestamps, and command output; the owner validation supplied for closure did not include those identifiers in the repository.
3. No approved authoritative/versioned exchange calendar and exceptional-session status source is implemented.
4. Live SSI and Supabase checks require external credentials; an offline run must report `UNKNOWN`, not claim live verification.

## Next step

Begin Phase 1 specification for shared strategy rules and point-in-time backtesting.
