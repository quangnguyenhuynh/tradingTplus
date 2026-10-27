# src/providers/ssi

Verified v3 provider contract and readiness registry; only daily datasets are production-ready.


## Guarded manual intraday pilot

`stock-intraday` now supports exactly one explicit symbol and Vietnam trading date. Default/`--dry-run` is READ-ONLY; only `--write` authorizes the guarded raw → clean insert sequence. SSI credentials are needed; Supabase service credentials enable read-only eligibility/conflict preflight and are required for writes. Without DB configuration, dry-run reports `NOT_RUN_NO_CREDENTIALS`, unknown planned counts and `write_ready=false`.

```bash
python main.py stock-intraday 20/10/2026 --symbols SSI
python main.py stock-intraday 20/10/2026 --symbols SSI --write
```

The second command is **owner-only after reviewing dry-run/preflight**. No ranges, ALL/wildcards, omitted scope, multiple symbols or future dates. Both persisted master statuses must be active. Source is only `ssi_v3`, timeframe only `1m`; canonical value is exact `ohlc.value`, with missing/invalid values blocking this pilot and no estimation fallback. Identical existing rows are skipped; differing canonical clean rows or raw key/source/payload conflicts block. No force overwrite. Raw is confirmed before clean; a partial/ambiguous write exits nonzero and requires scoped inspection then a safe rerun. Cross-table atomicity is not promised. Completeness remains UNVERIFIED. Other intraday ingest/backfill/refill/streaming commands and the schedule remain disabled. Features/signals/backtests never run from this pilot.

See [runbook](../../../docs/STOCK_INTRADAY_PIPELINE.md) for sequence, idempotency, partition behavior, recovery and owner verification. The inspector remains entirely read-only; registry readiness remains preview, with no generic production factory.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `base.py`
- `capabilities.py`
- `registry.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.

## Future integrations

Intraday: the verified preview adapter is reused by the isolated manual pilot. Registry readiness remains preview with no generic production factory. Unattended ingest/schedules/backfill remain disabled; see the runbook for guards, provenance and completeness limitations.

Master integration belongs in `src/ingest/master/` with dedicated verified provider adapters/mappings. Preserve operator-controlled statuses; do not infer master lists from price history or auto-sync during ingest. Streaming belongs in `src/ingest/streaming/` with a separately verified protocol and authentication contract; historical offline payload decoders are not evidence of v3 protocol compatibility. Restore schedules only in a separately reviewed capability implementation.

For a future SSI v4: add a client under `src/providers/ssi/clients/`, an adapter satisfying `DataSourceAdapter.fetch()` / `AdapterResult` under `adapters/`, a versioned `src/contracts/mappings/ssi_v4.json`, and per-dataset registry entries. Supply raw-source identity in adapter results, verify semantics and fixture parity, then mark only verified datasets ready. Business services must not select endpoint versions or silently fall back. V4 is not implemented here.

## Multi-page SSI v3 intraday preview (read-only)

The REST inspector stock-intraday/native intraday-ohlc routes now use the shared preview adapter and download successive pages from the requested start until explicit termination or failure/bound. `--limit` limits display only; `--full-json` includes every received raw page and clean candidate. `--max-pages` defaults to 100 (1–1000); hitting the bound, repeated pages, inconsistent totals or request failures return FAILED/exit 1 and retain received evidence. Other daily/index/catalog inspector routes keep their single-page behavior.

Owner-provided live SSI excerpts for 2026-10-20 verify `ohlc.tradingDate` in `YYYY/MM/DD HH:mm:ss`, source `ohlc.value`, and terminal `{"code":204,"msg":"No Content"}`. This exact source-local timestamp is explicitly interpreted in `Asia/Ho_Chi_Minh` and normalized to UTC; valid explicit-offset forms remain supported. The legacy `time` alias still requires an explicit timezone. Date-only/time-only and arbitrary naive formats remain rejected; no request-date fabrication or minute shifting.

Canonical v3 `value` is **SSI-reported intraday candle value**, parsed exactly as a nonnegative signed-BIGINT integer without float conversion. There is **no calculated estimate or fallback**. Absent/null/empty source value stays NULL with SOURCE_VALUE_MISSING; malformed/non-finite/fractional/negative/overflow value rejects the candidate. Zero stays zero. Source-value presence, numeric validity and preservation are reported separately from independently verified market-data semantics (still false).

The verified 204/No Content envelope terminates OHLC 1m paging only without conflicting payload/error markers and after metadata/count checks. Its original envelope is retained and termination is provider_no_content_204. Short nonempty pages never terminate by themselves; repeats, wrong totals, malformed/errors and page-limit truncation still fail. --limit controls display only; --full-json retains received raw pages, candidates and diagnostics.

The supplied day had 226 unique rows over 23 nonempty pages then page 24, descending order, 135 morning/90 afternoon/one 14:45 candle. These are owner-reported observations for that day, not a universal count or a formula rule. Only two real candle objects and the terminal envelope were supplied; offline replay verifies those 2/2 without reconstructing missing rows. Agent live rerun: NOT_RUN (no credentials). Bar-start/end, independent value/turnover semantics and market completeness remain unverified. Unattended ingestion/scheduling remains disabled; the inspector preview performs zero database reads/writes. The isolated manual pilot is described above.

See the [runbook and promotion checklist](../../../docs/STOCK_INTRADAY_PIPELINE.md) for field mappings, paging, validation/session/gap rules, source limitations and separate promotion steps.

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --from-date 2026-10-01 --to-date 2026-10-19 --page-size 100 --max-pages 100 --limit 5
python scripts/inspectors/ssi_rest/inspect.py run intraday-ohlc --symbol SSI --date 2026-10-19 --ascending --limit 5
```

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --page-size 10 --max-pages 100 --limit 5
```

## Verified security master

`master_v3.py` implements shared strict `securitiesByBoard` fetch/mapping for HOSE/HNX/UPCOM. Symbols/securities are guarded READY; both index capabilities remain unchanged BLOCKED. No authoritative provider total: market completeness UNVERIFIED. All instrument types retained; no automatic eligibility. [Mapping, anomaly guards, evidence and owner recovery](../../ingest/master/README.md).
