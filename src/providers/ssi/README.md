# src/providers/ssi

Verified v3 provider contract and readiness registry; only daily datasets are production-ready.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `base.py`
- `capabilities.py`
- `registry.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.

## Future integrations

Implement verified intraday mapping/fetching in `src/providers/ssi/adapters/` and orchestrate it only in `src/ingest/stock_intraday/`. The future input is a separately verified SSI v3 1m response, with explicit units, timestamp/bar conventions, symbol/date identity and raw traceability. The output must satisfy the existing `stock_intraday` canonical contract (`symbol`, aware market `time`, `timeframe='1m'`, nullable typed OHLCV/value and price context); preserve raw payloads, reject invalid timestamps and validate before clean writes. No response aliases are assumed from the retired API. Re-enable only after adapter, timestamp/session, pagination, idempotency, scope, no-data and no-partial-write tests pass.

Master integration belongs in `src/ingest/master/` with dedicated verified provider adapters/mappings. Preserve operator-controlled statuses; do not infer master lists from price history or auto-sync during ingest. Streaming belongs in `src/ingest/streaming/` with a separately verified protocol and authentication contract; historical offline payload decoders are not evidence of v3 protocol compatibility. Restore schedules only in a separately reviewed capability implementation.

For a future SSI v4: add a client under `src/providers/ssi/clients/`, an adapter satisfying `DataSourceAdapter.fetch()` / `AdapterResult` under `adapters/`, a versioned `src/contracts/mappings/ssi_v4.json`, and per-dataset registry entries. Supply raw-source identity in adapter results, verify semantics and fixture parity, then mark only verified datasets ready. Business services must not select endpoint versions or silently fall back. V4 is not implemented here.

## Multi-page SSI v3 intraday preview (read-only)

The REST inspector stock-intraday/native intraday-ohlc routes now use the shared preview adapter and download successive pages from the requested start until explicit termination or failure/bound. `--limit` limits display only; `--full-json` includes every received raw page and clean candidate. `--max-pages` defaults to 100 (1–1000); hitting the bound, repeated pages, inconsistent totals or request failures return FAILED/exit 1 and retain received evidence. Other daily/index/catalog inspector routes keep their single-page behavior.

SSI credentials were unavailable for verification: live NOT_RUN. V3 source semantics remain PROVISIONAL and completeness always UNVERIFIED. Only full source timestamps with explicit timezone normalize to UTC; naive/time-only/date-only values are rejected without request-date fabrication. Price/volume units are not certified; estimated value reuses round(close * volume) while source value stays raw. Production intraday CLI/scheduling remains disabled; preview makes zero Supabase reads/writes.

See the [runbook and promotion checklist](../../../docs/STOCK_INTRADAY_PIPELINE.md) for field mappings, paging, validation/session/gap rules, source limitations and separate promotion steps.

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --from-date 2026-10-01 --to-date 2026-10-19 --page-size 100 --max-pages 100 --limit 5
python scripts/inspectors/ssi_rest/inspect.py run intraday-ohlc --symbol SSI --date 2026-10-19 --ascending --limit 5
```
