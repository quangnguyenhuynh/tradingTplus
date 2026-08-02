# Phase 0 validation report

**Decision: BLOCKED**  
**Repository baseline:** `f80244bb350d3876762532241e372e0f0d2d1f71` (PR #116)  
**Offline validation date:** 2026-08-02  
**Environment:** Python 3.11-compatible test environment; deterministic fixtures; no SSI/Supabase/GitHub credentials or linked Supabase project.

Phase 0 is not complete. Offline pagination, long-history feature parity, and the repository atomic-replace contract have evidence, but the required SSI PDF was unavailable and live source/database/migration evidence could not be collected. No production query or mutation was attempted.

## Offline pagination evidence

All PostgREST feature and completeness readers are exercised with stable ordering, a requested size of 1,000, a simulated server cap of 500 or 400, short final pages, and terminal empty pages. Offsets advance by the number actually returned. Tests retain symbol/timeframe/time/date filters, reject non-positive page sizes, exercise exact limits, and reject repeated pages. The SSI page-index client separately continues after a short capped page, honors `totalRecord`, and rejects a repeated page.

The 251-session fixture contains seven candles per observed date. A 1,747-row server cap splits the oldest selected (250th) date across two descending pages. The reader returns all seven candles for that date, exactly 250 dates, no candle from the 251st older date, and no duplicate boundary candle.

Completeness fixtures read 1,205 symbols/rows through a 400-row cap (four data pages plus an empty page) without truncation.

## Long-history parity evidence

Comparison occurs after production serialization. Every persisted feature column is compared; symbol, timeframe, time, integers, booleans, and NULLs are exact. Floats use absolute tolerance `1e-6` or relative tolerance `1e-9`, matching the six-decimal application serialization. `last_updated_at` is the only excluded audit field.

| Timeframe | Full source | Bounded source | Target | Maximum absolute difference | Maximum relative difference |
| --- | ---: | ---: | ---: | ---: | ---: |
| `1d` | 1,501 weekday rows (>5 years) | 1,306 rows (production five-year window) | final date | 0 for every float column | 0 for every float column |
| `15m`, 200 sessions | 15,060 `1m` rows / 251 dates | 12,000 rows | final date | 0 for every float column | 0 for every float column |
| `15m`, 250 sessions | 15,060 `1m` rows / 251 dates | 15,000 rows | final date | 0 for every float column | 0 for every float column |
| `60m`, 200 sessions | 15,060 `1m` rows / 251 dates | 12,000 rows | final date | 0 for every float column | 0 for every float column |
| `60m`, 250 sessions | 15,060 `1m` rows / 251 dates | 15,000 rows | final date | 0 for every float column | 0 for every float column |

Fixtures have deterministic non-constant OHLCV/value variation, morning and afternoon candles, and a lunch break. Aggregation tests separately prove no lunch or Vietnam-date crossing. At a 1,000-row request size, intraday full needs 16 data pages, the 200-session scope 12, and the production 250-session scope 15; bounded modes do not default to full history. The daily bounded read removes 195 rows, although both full and bounded fixtures require two data pages at that page size.

The evidence supports retaining 250 observed sessions. The 200-session fixture also matches this deterministic target, but it is not the production default and this test alone is not a general proof that 200 is sufficient for every real series.

## Atomic replace and migrations

The migration remains service-role-only, `SECURITY DEFINER`, with empty `search_path`, exact symbol/timeframe/half-open-range validation, duplicate/empty rejection, transactional delete/insert, and rollback protection. Normal GitHub Actions runs the complete suite with PostgreSQL 16 and `TEST_DATABASE_URL`; the integration test is not configured to skip.

Production status is **UNKNOWN**. No linked Supabase project or credentials were available, so pending migration status, function privileges, required indexes, and `raw_intraday.payload` production metadata were not queried. Neither authorized migration was applied here. No production rows were changed. Historical payload remains intentionally unbackfilled; new ingest records retain the complete semantic candle object in nullable JSONB.

## SSI contract/evidence matrix

The requested `SSI_FastConnectData_Specs_v2.2.pdf` was not available in the repository or accessible attachment paths. Therefore no behavior is classified as SSI-documented solely from repository prose.

| Critical item | Classification | Evidence / blocker |
| --- | --- | --- |
| `DailyStockPrice` endpoint and fields | `INFERRED_BY_CODE` | Canonical in current client/mapper; PDF and live response unavailable. |
| `DailyOHLC` comparison behavior | `INFERRED_BY_CODE` | Inspector/client treat it as comparison-only; not live observed. |
| `IntradayOHLC` resolution `1` fields/units | `INFERRED_BY_CODE` | Client/mapper contract only; not live observed. |
| SSI pagination/caps | `INFERRED_BY_CODE` | Defensive client behavior and offline response fixtures only. |
| `raw_daily.payload` equality/hash | `UNKNOWN` | No production raw row or live source object. |
| `raw_intraday.payload` nested/unknown-field retention | `INFERRED_BY_CODE` | Mapper tests/code; production migration/sample unverified. |
| Intraday timestamp meaning | `INFERRED_BY_CODE` | Vietnam parsing and UTC storage implemented; source semantics not documented/observed here. |
| Intraday volume meaning | `UNKNOWN` | Required PDF/live evidence unavailable. |
| Intraday value | `INFERRED_BY_CODE` | Clean value is estimated `round(close * volume)`, not claimed as SSI turnover. |
| Weekend response | `UNKNOWN` | Authentication/live request unavailable. |
| Official weekday holiday response | `UNKNOWN` | Authentication/live request and authoritative calendar unavailable. |

No item is `DOCUMENTED_AND_OBSERVED`, `DOCUMENTED_NOT_OBSERVED`, or `OBSERVED_NOT_DOCUMENTED` in this run because neither the supplied document nor live access was available.

## Live reconciliation

No live sample scope was selected or queried: selecting exact existing liquid/low-liquidity symbols, closed buckets, feature dates, and production hashes requires read-only access to the linked database, while source comparison requires SSI authentication. Consequently daily raw-to-clean, intraday raw-to-clean, independent clean-to-feature reproduction, weekend behavior, and official-holiday behavior remain blocked. This report does not substitute fabricated dates or payloads.

## Completeness gate

Offline tests cover a normal structurally complete day, isolated missing interval, duplicate, missing afternoon session, long structural gap, low-liquidity-style isolated empty buckets, and capped pagination over 1,000 rows. Reports expose counts, first/last times, duplicates, missing intervals/minutes, gap class, and reasons without a universal 226-candle rule. Public `OK/PARTIAL/FAILED` summaries remain compatible.

The repository has no approved authoritative exchange calendar/status design. It cannot safely distinguish a weekday official holiday from a trading day with no data or a source/authentication failure based on stored rows alone. No holiday list was invented. This is a Phase 0 blocker.

## Database and backfill impact

No new migration, production write, ingest, replace, backfill, payload synthesis, or feature rebuild was performed. No feature formula changed, so no rebuild is needed. `schema.sql` plus ordered migrations are canonical; the redundant historical `docs_db_schema.md` snapshot was removed.

## Unresolved blockers

1. Supplied SSI PDF unavailable.
2. SSI credentials/live source responses unavailable.
3. Linked production Supabase project and read-only credentials unavailable.
4. Production status and verification of the two authorized migrations unavailable.
5. No authoritative, versioned exchange-calendar/status source is approved.
6. GitHub authentication is unavailable, so CI jobs cannot be inspected and Issue #110 cannot be commented on or closed.

Issue #110 and Phase 0 must remain open.
