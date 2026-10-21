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
