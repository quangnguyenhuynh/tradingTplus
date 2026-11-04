# SSI v3 daily numeric precision audit and implementation

[Tiếng Việt](DAILY_NUMERIC_PRECISION.vi.md)

## Investigation and evidence

Base `dev`: `7eb92be8a67c543a33865b7d3f1d044b4473beed` (PR #190 merged). Audited contracts/registry/transforms/engine/derived, stock and index services/adapters/REST clients, daily validators, existing V1 RPC and migrations, actual database catalog, CLI, inspector and tests before coding.

Confirmed defects: Stock monetary fields used integer transforms; V1's local integer check rejected finite fractions. Index numeric fields and both daily validators used float. `to_int()` passed through float. The default HTTP/SDK JSON decoders could round numeric literals before mapping. Ordinary SDK JSON encoding cannot carry Decimal directly. Default Decimal precision 28 can round derived sums/subtractions. Index relative tolerances could hide meaningful money differences. V1's retained-value SQL required monetary inputs to be integers. Index validation allowed a missing core index level and did not enforce integral counts. Multiple index records could overwrite the same daily identity.

Read-only production catalog inspection confirmed unscaled NUMERIC daily market columns; stock identity `(symbol,trading_date)`, index identity `(index_code,trading_date)`; stock RAW uniqueness includes source/hash, index RAW uniqueness uses `(index_code,trading_date,data_hash)`. Existing Stock V1 RPC is installed as SECURITY INVOKER. `stock_data_quality_logs` has its existing current-issue unique key. No `index_data_quality_logs`, index validation_status, index CLEAN source/raw/audit columns were found. No schema change was executed there.

Scoped production SELECT evidence, 4 November 2026 (Vietnam):

| Stock / date | RAW totalMatchValue (JSON string) | CLEAN total_match_val |
| --- | --- | --- |
| BID / 2025-03-12 | 162662895000.001 | missing |
| TCB / 2025-03-12 | 303651874999.999 | missing |
| VCB / 2025-03-12 | 506132139999.992 | missing |
| TCB / 2025-04-29 | 478199435000.012 | missing |

| VNINDEX date | v3 RAW netPurchasesForeignValue | CLEAN net_foreign_purchase_value |
| --- | --- | --- |
| 2026-03-17 | -669526974313.6 | -669526974313.6 |
| 2026-07-28 | -1978131345916.1 | -1978131345916.1 |
| 2026-08-07 | -76067038810.7 | -76067038810.7 |

The three Index samples match by exact SQL numeric semantics. Legacy `SSI_DailyIndex` RAW also exists on these dates without the v3 field. This is provenance evidence, not proof of corrupted Index history. The owner-reported 418 fractional Stock RAW rows, 219 affected RAW-only keys, 17 Index samples and historical VNIndex/VNINDEX counts were not recomputed across the entire repository history in this task; they are observations, not acceptance constants. Recalculate for the exact proposed rerun scope.

Tests use realistic stored v3 field shapes and the confirmed monetary examples. OHLC/other fields reused from the existing SSI fixture are representative; tests do not claim complete verbatim BID/TCB/VCB responses.

## Classification and versions

Daily mapping/contract version is **3.0.0**. Stock policy is **stock_daily_validation_v1.1.0**; Index validator policy is **index_daily_numeric_v1.0.0**. Public function names/signatures and EOD CLI names remain compatible; native canonical daily monetary/price values are now Decimal and discrete quantities int. Consumers pinning an older mapping/contract version must deliberately update; the registry exposes the current declarations, while persisted old reports remain readable with their original versions.

PostgreSQL NUMERIC is exact decimal storage, not proof that Python float parsing preserved the original digits. Monetary values accept finite fractions without rounding, truncation, scale conversion or fabricated zero. Discrete quantities require exact integrality. Signed changes/net values may be negative. Units and percentage scale remain unchanged. Unsupported fields remain NULL and never gain invented source mappings.

The complete field matrix follows. SQL market column types remain NUMERIC in both datasets. Mandatory Stock OHLC stays positive even for explicit zero/missing matches; V1 does not infer a no-trade price. Missing core match values remain NULL + PARTIAL, consistent with existing nullable contracts. Optional Stock average-price validation retains the existing activity-sensitive zero rule.

### stock_daily

| Field | Unit | Semantics | Sign / required policy | Transform |
| --- | --- | --- | --- | --- |
| `price_change` | VND/share | level_price_percentage | signed | decimal |
| `per_price_change` | percent | level_price_percentage | signed | decimal |
| `ceiling_price` | VND/share | level_price_percentage | >= 0; optional | unsupported -> NULL |
| `floor_price` | VND/share | level_price_percentage | >= 0; optional | unsupported -> NULL |
| `ref_price` | VND/share | level_price_percentage | >= 0; optional | unsupported -> NULL |
| `open_price` | VND/share | level_price_percentage | > 0; mandatory | decimal |
| `highest_price` | VND/share | level_price_percentage | > 0; mandatory | decimal |
| `lowest_price` | VND/share | level_price_percentage | > 0; mandatory | decimal |
| `close_price` | VND/share | level_price_percentage | > 0; mandatory | decimal |
| `average_price` | VND/share | level_price_percentage | existing optional price rule | decimal |
| `close_price_adjusted` | VND/share | level_price_percentage | >= 0; optional | unsupported -> NULL |
| `total_match_vol` | shares | discrete_quantity | >= 0 when present; NULL -> PARTIAL | exact_int |
| `total_match_val` | VND | monetary | >= 0 when present; NULL -> PARTIAL | decimal |
| `total_deal_vol` | shares | discrete_quantity | >= 0; optional | exact_int |
| `total_deal_val` | VND | monetary | >= 0; optional | decimal |
| `total_traded_vol` | shares | discrete_quantity | >= 0; optional | derived exact_int |
| `total_traded_value` | VND | monetary | >= 0; optional | derived decimal |
| `foreign_buy_vol_total` | shares | discrete_quantity | >= 0; optional | exact_int |
| `foreign_sell_vol_total` | shares | discrete_quantity | >= 0; optional | exact_int |
| `foreign_buy_val_total` | VND | monetary | >= 0; optional | decimal |
| `foreign_sell_val_total` | VND | monetary | >= 0; optional | decimal |
| `foreign_remaining_room` | shares | discrete_quantity | >= 0; optional | exact_int |
| `foreign_total_room` | shares | discrete_quantity | >= 0; optional | exact_int |
| `net_foreign_vol` | shares | discrete_quantity | signed | derived exact_int |
| `net_foreign_val` | VND | monetary | signed | derived decimal |
| `total_buy_trade` | trades | discrete_quantity | >= 0; optional | exact_int |
| `total_buy_trade_vol` | shares | discrete_quantity | >= 0; optional | exact_int |
| `total_sell_trade` | trades | discrete_quantity | >= 0; optional | exact_int |
| `total_sell_trade_vol` | shares | discrete_quantity | >= 0; optional | exact_int |

### index_daily

| Field | Unit | Semantics | Sign / required policy | Transform |
| --- | --- | --- | --- | --- |
| `index_value` | index points | level_price_percentage | > 0; mandatory | decimal |
| `index_change` | index points | level_price_percentage | signed | decimal |
| `index_change_percentage` | percent | level_price_percentage | signed | decimal |
| `total_trade_volume` | provider volume | discrete_quantity | >= 0; optional | exact_int |
| `total_trade_value` | provider value | monetary | >= 0; optional | decimal |
| `total_match_volume` | provider volume | discrete_quantity | >= 0; optional | exact_int |
| `total_match_value` | provider value | monetary | >= 0; optional | decimal |
| `total_deal_volume` | provider volume | discrete_quantity | >= 0; optional | exact_int |
| `total_deal_value` | provider value | monetary | >= 0; optional | decimal |
| `total_advance_stock` | stocks | discrete_quantity | >= 0; optional | exact_int |
| `total_ceiling_stock` | stocks | discrete_quantity | >= 0; optional | exact_int |
| `total_decline_stock` | stocks | discrete_quantity | >= 0; optional | exact_int |
| `total_floor_stock` | stocks | discrete_quantity | >= 0; optional | exact_int |
| `total_no_change_stock` | stocks | discrete_quantity | >= 0; optional | exact_int |
| `total_prop_buy_volume` | provider volume | discrete_quantity | >= 0; optional | exact_int |
| `total_prop_buy_value` | provider value | monetary | >= 0; optional | decimal |
| `total_prop_sell_volume` | provider volume | discrete_quantity | >= 0; optional | exact_int |
| `total_prop_sell_value` | provider value | monetary | >= 0; optional | decimal |
| `total_foreign_buy_volume` | provider volume | discrete_quantity | >= 0; optional | exact_int |
| `total_foreign_buy_value` | provider value | monetary | >= 0; optional | decimal |
| `total_foreign_sell_volume` | provider volume | discrete_quantity | >= 0; optional | exact_int |
| `total_foreign_sell_value` | provider value | monetary | >= 0; optional | decimal |
| `net_foreign_purchase_volume` | provider volume | discrete_quantity | signed | exact_int |
| `net_foreign_purchase_value` | provider value | monetary | signed | decimal |

## Exact mapping, arithmetic and transport

New allowlisted `decimal` and `exact_int` transforms reject bool, nonfinite values and invalid numeric strings. Exact integer parsing checks Decimal integrality before int conversion. Alias comparison uses mathematical Decimal/int equality; conflicting non-null aliases and ambiguous failed aliases still reject. Explicit unit multipliers remain explicit; none are added by this change.

Only daily mappings opt in. Legacy `to_int()`/`to_float()` remain unchanged for compatibility and are not referenced by active daily mappings. No current mapping still references the legacy int transform. Intraday, master, features and other datasets retain their existing behavior.

Production daily HTTP paths parse original response bytes using `parse_float=Decimal`; JSON integers remain exact Python integers. Duplicate keys and nonfinite JSON constants fail closed. Inspector daily HTTP parsing and JSON output also preserve exact numeric tokens. Existing injected/predecoded float inputs can preserve only `Decimal(str(float_value))`, not lost upstream digits: mapping reports expose `predecoded_float_source_fields` and mapped `predecoded_float_fields`. Mapped float inputs receive PREDECODED_FLOAT_PRECISION_UNVERIFIED warnings (Stock PARTIAL, Index warning), never an assertion that changing type recovered precision. Historical RAW that was rounded before storage cannot establish the original wire value without new source evidence.

Stock derived sums/differences use operand-dependent local Decimal precision, not the default precision 28. NULL inputs propagate NULL. SQL recalculates derived fields from final retained inputs. No float conversion, quantization or rounding tolerance is used for money/count consistency. Existing Stock price/change tolerances remain legacy checks, not a newly verified SSI tick/precision rule.

The persistence path is: HTTP bytes -> immutable semantic RAW -> exact mapping/policy/derived -> exact JSON number tokens inside **RPC text arguments** -> PostgreSQL `::jsonb`/NUMERIC -> SQL readback. The normal SDK encoder encodes only the outer strings/metadata; it never converts Decimal to float or replaces numeric RAW values with strings. Source JSON strings stay strings; source JSON numbers stay numbers. No custom SDK monkey-patch or new dependency.

RAW remains JSONB evidence, not an archive of HTTP whitespace/byte formatting. Hashes retain the previous canonical representation for existing string-only payloads. Exact numeric decoding can produce a new hash where the old representation was rounded or had different numeric lexical scale; this creates a separate immutable version, never updates old RAW. New exact-path reruns are deterministic. Index RAW conflict identity excludes source: a same-hash conflict with different provenance fails readback and preserves legacy evidence instead of overwriting it.

## Stock validation and logs

Core identity/OHLC/populated match failures still reject CLEAN. The explicit optional allowlist/quarantine rules from V1 remain. Negative room becomes NULL with BELOW_MINIMUM; invalid optional quantities become NULL, never fractional shares in CLEAN. Mandatory fractional match volume rejects. Finite nonnegative fractional monetary inputs are kept exactly and receive WARNING `FRACTIONAL_MONETARY_VALUE` / action `KEEP_EXACT_DECIMAL`, making the attempt PARTIAL. This is a traceable precision-semantics warning, not an assertion that monetary fractions are invalid. Warnings attach to mapped monetary inputs; derived values inherit their input evidence.

`persist_stock_daily_validation_v1` retains its identity and atomic CLEAN/log transaction. Its monetary retention rule now permits finite nonnegative decimals; discrete fields remain integral. The new text wrapper delegates to it. It accepts policy 1.0.0 for old clients and 1.1.0 for the matching app; do not mix writers during deployment. Existing VALID rows cannot be overwritten by REJECTED or silently downgraded by PARTIAL. A new fractional-money attempt against VALID is explicitly rejected with CLEAN_VALID_DOWNGRADE_BLOCKED for owner review, never forced through.

Current issue identity remains `(symbol,trading_date,check_name='stock_daily_validation_v1')`, timeframe 1d. New policy/version/raw/decision fingerprints archive changed prior snapshots once; repeated identical attempts do not grow duplicate history. Old REJECTED policy 1.0.0 evidence remains in history when new policy accepts PARTIAL. Issue-free VALID creates no new log and resolves existing current issues. Historical NULL validation_status remains unverified. Known valid old optional inputs can survive missing new values with KEEP_EXISTING_FIELD/preserved_fields and previous_clean_raw_hash; invalid legacy values do not survive. Derived fields are recomputed, never falsely reported as retained. previous_clean_raw_hash is populated only for one semantic JSONB match; equivalent numeric RAW versions make it NULL with previous_clean_raw_hash_match_count, rather than arbitrarily selecting LIMIT 1.

RAW commits first. CLEAN/log commit atomically afterward, with readback and no automatic ambiguous write retry. A failed acknowledgment or log/readback failure reports failure; RAW may remain. A lost HTTP acknowledgment can follow a successful DB commit: reconcile first, then explicitly rerun. Summary errors identify the new migration when exact RPCs are missing. Existing counters/backfill aggregation remain available.

## Index-specific decisions

Index remains a separate pipeline. A finite positive level, correct requested date and consistent identity are mandatory. The verified endpoint can omit its own code; request-scoped context remains the existing identity source, while any supplied index/indexCode/indexId must agree after uppercase normalization. Case-only identities are equivalent for comparison. Multiple source rows reject all ambiguous CLEAN writes while preserving RAW.

All present numeric fields must be finite; volumes/stock counts must be integral; totals/buy/sell fields nonnegative; signed changes and net foreign values can be negative. Core or optional numeric errors reject the whole Index row. **Index optional-field quarantine is deliberately not added**: no suitable persisted Index quality/status contract exists, and this task does not create a parallel log framework or repurpose Stock logs. Monetary fractions alone remain valid for Index, consistent with existing monetary semantics. This does not certify independently verified SSI precision or market completeness.

Total = match + deal and net = buy - sell compare exact mathematical values, with **zero numeric tolerance**. Differences are explainable warnings; source totals are preserved, never recomputed to make them pass. CLI status becomes PARTIAL when warnings exist. The Index RPC serializes `(index_code,date)`, preserves independently valid old optional inputs against NULL, checks final readback and returns preserved_fields. It rechecks total/net relationships after retention and reports merge_issues with exact decimal strings, disclosing mixed provenance. Rejected input never reaches the CLEAN RPC. Existing CLEAN has no persisted Index validation status or RAW hash; warnings/current-versus-resolved state are not durably stored for Index. Export summaries/audits and treat historical Index CLEAN validation/provenance as UNVERIFIED.

## Read-only diagnostics

The new command reads only persisted data through `read_daily_numeric_scope_v1`, a restricted STABLE invoker SELECT function returning exact JSON **text**. The SDK therefore cannot round RAW/CLEAN numeric tokens before the audit parses them with Decimal. No SSI client, RAW/CLEAN/log/feature write or fallback to lossy table reads.

```bash
python main.py daily-numeric-quality --dataset stock_daily --identifiers BID TCB VCB --date 12/03/2025 > stock-20250312-quality.json
python main.py daily-numeric-quality --dataset stock_daily --identifiers TCB --date 29/04/2025
python main.py daily-numeric-quality --dataset index_daily --identifiers VNINDEX --date 17/03/2026
python main.py daily-numeric-quality --dataset index_daily --identifiers VNINDEX --from 28/07/2026 --to 07/08/2026 > vnindex-quality.json
```

Use 1–50 explicit identifiers, at most 31 calendar days, 100-row pages and a 10,000-row per-kind cap. Invalid scope fails before constructing a DB client. Stable identity/order/exact-count checks detect duplicates, count changes and truncation. Narrow scope on failures. Pages are observed reads, not one cross-request snapshot; pause writers for authoritative reconciliation.

Reports cover RAW-only, CLEAN-only, source-version numeric differences, valid monetary fractions, nonintegral quantities, sign/mapping/validation failures, missing optional fields, case/provenance conflicts, unverified historical CLEAN, and current/resolved Stock issues with history. Counts include dataset/source/canonical identifier/date/field/code/mapping/policy version. One RAW can have several observations; multiple RAW versions are not distinct trading days. Unsupported legacy sources are flagged, never remapped as v3. VNIndex/VNINDEX comparisons canonicalize identity without changing stored records. Multiple case-variant CLEAN identities are marked ambiguous, not arbitrarily selected.

A RAW/CLEAN mismatch is an observed source-version difference, not proof of corruption: CLEAN can reflect another RAW or documented retained inputs. Stock clean_matches_this_raw and issue provenance help explain it; Index cannot prove that provenance from its schema. RAW-only replay cannot reconstruct old DB/HTTP/log failures or multi-record response context. CLI financial observations use exact decimal strings where appropriate; source inspector/index-preview JSON retains numeric tokens. Parse numeric JSON with a Decimal-aware reader. Existing `stock-eod-quality` remains available but uses legacy SDK table decoding; its precision note directs exact audits to the new command.

## Owner migration, verification and rollback

New migration: [`20261104_daily_numeric_precision.sql`](../migrations/20261104_daily_numeric_precision.sql). The applied `20261103_stock_daily_quality_v1.sql` is unchanged. Supabase CLI is unavailable locally, so the new file follows the repository's existing date-prefix convention manually.

The migration replaces the existing Stock V1 RPC and adds four functions: persist_daily_raw_numeric_v1, persist_stock_daily_numeric_v1, persist_index_daily_numeric_v1 and read_daily_numeric_scope_v1. All are SECURITY INVOKER, empty search_path, PUBLIC/anon/authenticated execute revoked, service_role execute granted. No new table, column, status/index structure, NUMERIC type change, historical market/status rewrite or backfill. NOTIFY reloads the PostgREST schema cache. Five-second migration lock timeout; no automatic production application.

Deployment order: review PR/migration; pause both daily writers and drain runs; owner applies migration after V1; verify catalog/privileges and RPC cache visibility; deploy matching app; run read-only scope audits; explicitly choose one Stock test rerun; verify exact CLEAN/status/logs; run Index test only if audit evidence justifies it. Only then plan further bounded historical reruns. New app before migration fails safely; do not run old/new writers concurrently. API success depends on actual deployment/credentials, not local tests.

```sql
SELECT table_name,column_name,data_type,numeric_precision,numeric_scale
FROM information_schema.columns WHERE table_schema='public'
 AND table_name IN ('stock_daily','index_daily') AND data_type='numeric'
ORDER BY table_name,ordinal_position;
SELECT p.proname,p.prosecdef,p.provolatile,p.proconfig,
 has_function_privilege('anon',p.oid,'EXECUTE') AS anon_execute,
 has_function_privilege('authenticated',p.oid,'EXECUTE') AS authenticated_execute,
 has_function_privilege('service_role',p.oid,'EXECUTE') AS service_execute
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='public' AND p.proname IN
 ('persist_stock_daily_validation_v1','persist_daily_raw_numeric_v1',
  'persist_stock_daily_numeric_v1','persist_index_daily_numeric_v1','read_daily_numeric_scope_v1');
SELECT t,has_table_privilege('service_role','public.'||t,'SELECT,INSERT,UPDATE') AS clean_log_access
FROM unnest(ARRAY['stock_daily','index_daily','stock_data_quality_logs']) t;
SELECT t,has_table_privilege('service_role','public.'||t,'SELECT,INSERT') AS raw_access
FROM unnest(ARRAY['stock_raw_daily','index_raw_daily']) t;
SELECT pg_get_functiondef('public.persist_stock_daily_validation_v1(text,date,text,jsonb,jsonb)'::regprocedure);
```

Expected invoker (`prosecdef=false`), service execute true, anon/authenticated false; read RPC volatility `s`. Existing Stock log sequence USAGE and schema USAGE remain necessary. Review existing grants; migration does not widen table/RLS access.

Read-only precision verification for the operator's exact scope:

```sql
SELECT r.symbol,r.trading_date,r.source,r.data_hash,r.payload->>'totalMatchValue' AS raw_value,
 c.total_match_val::text AS clean_value,c.validation_status
FROM public.stock_raw_daily r LEFT JOIN public.stock_daily c USING(symbol,trading_date)
WHERE r.source='ssi_v3' AND r.symbol IN ('BID','TCB','VCB') AND r.trading_date=DATE '2025-03-12'
ORDER BY r.symbol,r.data_hash;
SELECT r.index_code,r.trading_date,r.source,r.payload->>'netPurchasesForeignValue' AS raw_value,
 c.net_foreign_purchase_value::text AS clean_value
FROM public.index_raw_daily r LEFT JOIN public.index_daily c
 ON upper(c.index_code)=upper(r.index_code) AND c.trading_date=r.trading_date
WHERE upper(r.index_code)='VNINDEX' AND r.source='SSI_v3_indexSummary'
 AND r.trading_date=DATE '2026-03-17';
SELECT symbol,trading_date,status,issue_count,details->>'policy_version' AS policy,
 details->'issues' AS issues,details->'history' AS history
FROM public.stock_data_quality_logs WHERE check_name='stock_daily_validation_v1'
 AND symbol IN ('BID','TCB','VCB') AND trading_date=DATE '2025-03-12';
```

Recalculate fractional RAW rows and affected distinct keys for a chosen explicit range before any rerun (change both dates deliberately; this example is one day):

```sql
WITH parsed AS (
 SELECT r.*,CASE WHEN (r.payload->>'totalMatchValue') ~ '^[+-]?[0-9]+([.][0-9]+)?([eE][+-]?[0-9]+)?$'
 THEN (r.payload->>'totalMatchValue')::numeric END AS value
 FROM public.stock_raw_daily r WHERE r.source='ssi_v3'
 AND r.symbol IN ('BID','TCB','VCB')
 AND r.trading_date BETWEEN DATE '2025-03-12' AND DATE '2025-03-12'
), fractional AS (SELECT * FROM parsed WHERE value>=0 AND value<>trunc(value))
SELECT count(*) AS fractional_raw_versions,
 count(DISTINCT(f.symbol,f.trading_date)) AS fractional_keys,
 count(DISTINCT(f.symbol,f.trading_date)) FILTER(WHERE c.symbol IS NULL) AS raw_only_keys
FROM fractional f LEFT JOIN public.stock_daily c USING(symbol,trading_date);
```

Rollback: pause writers, deploy the previous app deliberately, retain additive functions/RAW/log evidence. The updated V1 function still accepts old policy 1.0.0 and JSONB arguments, so an application rollback need not drop functions or restore old flawed integer-money retention. The prior app does not provide the new exactness guarantee. Optional function cleanup/restoration requires separate owner review after all callers stop. Never delete RAW/logs or relabel historical statuses to make deployment pass; migration rollback cannot undo later market writes.

## Narrow owner WRITE examples — not executed

Only after migration/deployment/audit review, using existing active-scope/eligible-day rules:

```bash
python main.py stock-eod-backfill --from 12/03/2025 --to 12/03/2025 --symbols BID --data-source ssi_v3
# Index only if the exact audit shows a reason to rerun:
python main.py index-eod-backfill --from 17/03/2026 --to 17/03/2026 --indexes VNINDEX --data-source ssi_v3
```

These call SSI and write source data. For Index backfill, inspect per-day/per-index status/errors: its existing top-level error_count is not a complete record-level diagnostic. No production rerun was performed by this task. Do not expand scope from historical counts alone, force a blocked VALID downgrade, or automatically rerun features/signals/backtests. Existing feature code does not automatically exclude Stock PARTIAL; consumers must handle NULL quarantines and validation status. Source correction can change inputs for a later separately authorized feature rerun.

## Verification report

Exact commands and file inventory are recorded below. Local PostgreSQL 17 was downloaded/extracted into /tmp and initialized as a disposable test cluster bound to 127.0.0.1:55432; no system package/repository dependency was added. Tests refuse production TEST_DATABASE_URL hosts. Existing GitHub CI supplies PostgreSQL 16 for independent verification.

Implemented code and tests do not constitute production correction. Production migration pending; source history pending owner-scoped revalidation/backfill; independent SSI precision/completeness semantics still require source verification. No live SSI request, production migration/backfill/feature write was made. Read-only catalog and seven scoped numeric examples were queried through the connected Supabase tool.

## Commands run and results

The URL below identifies this workspace disposable test cluster, never a production database.

```bash
source .venv/bin/activate
export TEST_DATABASE_URL=postgresql://agent@127.0.0.1:55432/postgres
python -m pytest -q tests/data_contracts tests/validation/test_daily_validator.py tests/validation/test_stock_daily_v1.py tests/validation/test_stock_daily_v1_postgres.py tests/validation/test_daily_numeric_postgres.py tests/validation/test_daily_numeric_diagnostics.py tests/database/test_daily_numeric_transport.py tests/database/test_stock_daily_quality_rpc.py tests/ingest/test_index_daily_pipeline.py tests/data_sources/test_ssi_v3_stock_daily.py tests/data_preview/test_v3_client.py tests/inspectors/test_ssi_api_mapping.py tests/test_app_controlled_timestamps.py tests/pipeline/test_backfill_pipeline.py tests/pipeline/test_stock_eod_pipeline.py
python -m pytest -q
python -m compileall -q main.py src scripts tests
python main.py --help
python main.py daily-numeric-quality --help
python main.py stock-eod-quality --help
python main.py stock-eod --help
python main.py stock-eod-backfill --help
python main.py index-eod --help
python main.py index-eod-backfill --help
python main.py index-preview --help
git diff --check
git diff --exit-code 7eb92be8a67c543a33865b7d3f1d044b4473beed -- migrations/20261103_stock_daily_quality_v1.sql
```

**Focused: 235 passed; full: 1,391 passed; 0 failed/0 skipped** with local PostgreSQL 17, including 34 daily migration/RPC tests and 8 real-SDK HTTP-mock encoder tests. Compile/8 CLI help/diff checks passed; the applied V1 migration is unchanged. No repository linter configuration; syntax/whitespace checks completed. PostgreSQL 16 CI evidence is recorded in the PR after push.

## File inventory

### Modified

- `README.md`
- `README.vi.md`
- `docs/CLI_REFERENCE.md`
- `docs/CLI_REFERENCE.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/DATA_PIPELINE.md`
- `docs/README.md`
- `docs/README.vi.md`
- `docs/SSI_DAILY_INDEX_MAPPING.md`
- `docs/STOCK_DAILY_QUALITY_V1.md`
- `docs/STOCK_DAILY_QUALITY_V1.vi.md`
- `docs/STOCK_EOD_PIPELINE.md`
- `docs/STOCK_EOD_PIPELINE.vi.md`
- `docs/backfill/README.md`
- `docs/backfill/README.vi.md`
- `migrations/README.md`
- `migrations/README.vi.md`
- `scripts/inspectors/ssi_rest/README.md`
- `scripts/inspectors/ssi_rest/README.vi.md`
- `scripts/inspectors/ssi_rest/client.py`
- `scripts/inspectors/ssi_rest/inspect.py`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/cli/__init__.py`
- `src/cli/parser.py`
- `src/contracts/README.md`
- `src/contracts/README.vi.md`
- `src/contracts/definitions.json`
- `src/contracts/derived.py`
- `src/contracts/engine.py`
- `src/contracts/mappings/ssi_v3.json`
- `src/contracts/transforms.py`
- `src/database/README.md`
- `src/database/README.vi.md`
- `src/database/client.py`
- `src/ingest/index_daily/README.md`
- `src/ingest/index_daily/README.vi.md`
- `src/ingest/index_daily/index_daily_mapper.py`
- `src/ingest/index_daily/index_daily_persistence.py`
- `src/ingest/index_daily/index_daily_preview.py`
- `src/ingest/index_daily/index_daily_service.py`
- `src/ingest/stock_daily/README.md`
- `src/ingest/stock_daily/README.vi.md`
- `src/ingest/stock_daily/daily_mapper.py`
- `src/ingest/stock_daily/daily_service.py`
- `src/providers/ssi/adapters/v3.py`
- `src/providers/ssi/clients/rest_v3.py`
- `src/quality/README.md`
- `src/quality/README.vi.md`
- `src/quality/stock_daily_diagnostics.py`
- `src/quality/validators/README.md`
- `src/quality/validators/README.vi.md`
- `src/quality/validators/daily_validator.py`
- `src/quality/validators/index_daily_validator.py`
- `src/quality/validators/stock_daily_v1.py`
- `tests/data_contracts/test_engine.py`
- `tests/data_preview/test_intraday_preview.py`
- `tests/data_preview/test_v3_client.py`
- `tests/database/test_stock_daily_quality_rpc.py`
- `tests/ingest/test_index_daily_pipeline.py`
- `tests/ingest/test_provider_boundary.py`
- `tests/inspectors/test_ssi_api_mapping.py`
- `tests/test_app_controlled_timestamps.py`
- `tests/validation/test_stock_daily_v1.py`
- `tests/validation/test_stock_daily_v1_postgres.py`

### Created

- `docs/DAILY_NUMERIC_PRECISION.md`
- `docs/DAILY_NUMERIC_PRECISION.vi.md`
- `docs/SSI_DAILY_INDEX_MAPPING.vi.md`
- `migrations/20261104_daily_numeric_precision.sql`
- `src/cli/quality.py`
- `src/contracts/numeric.py`
- `src/quality/daily_numeric_diagnostics.py`
- `src/quality/validators/index_daily_numeric.py`
- `tests/data_contracts/test_daily_exact_numeric.py`
- `tests/database/test_daily_numeric_transport.py`
- `tests/validation/test_daily_numeric_diagnostics.py`
- `tests/validation/test_daily_numeric_postgres.py`

No files deleted. The shared HTTP test fixture gains bytes for daily decoder checks; intraday algorithms remain unchanged.
