# Current state — SSI v3 only

Reviewed 21 October 2026 against `dev` commit `b5cb3276f367a0e50ded3c83967570f24b7480c6` (PR #178). Current and historical documentation were compared for the CLI restoration. Live SSI/Supabase checks were not run.

| Capability | Status |
| --- | --- |
| SSI v3 Stock Daily / Index Daily | ACTIVE |
| SSI v3 Stock Intraday ingestion | NOT_IMPLEMENTED |
| SSI v3 Master Data synchronization | NOT_IMPLEMENTED |
| SSI v3 Streaming / Orderbook | NOT_IMPLEMENTED |
| Stock technical, foreign and index features | ACTIVE |
| Historical Analog / Screener V1/V2 | RESEARCH_ACTIVE |
| SSI v2 REST / legacy SignalR connection | RETIRED |

The thin `main.py` entrypoint calls `src.cli`. CLI parsing and source/capability preflight precede service access. Domain handlers call `src.ingest` services, which use the provider registry, `src.contracts`, `src.quality`, and existing raw/clean persistence. `src.providers.ssi` has no ingest or database dependency. Contracts contain no endpoint-specific request logic.

`src.features.stock`, `.foreign`, and `.index` run independently on persisted clean data. `src.research.screener` and `.analogs` preserve their formulas, configurations, profiles and research storage contracts. Intraday ingestion being unavailable does not prevent features from reading historical clean 1m candles.

No schema, RPC, conflict-key, migration or production-data changes are part of this restructuring. Historical raw/clean/master/streaming/features and source provenance remain untouched. No migration or backfill is required. Ingest never starts features or research automatically.

## Future integrations

Implement verified intraday mapping/fetching in `src/providers/ssi/adapters/` and orchestrate it only in `src/ingest/stock_intraday/`. The future input is a separately verified SSI v3 1m response, with explicit units, timestamp/bar conventions, symbol/date identity and raw traceability. The output must satisfy the existing `stock_intraday` canonical contract (`symbol`, aware market `time`, `timeframe='1m'`, nullable typed OHLCV/value and price context); preserve raw payloads, reject invalid timestamps and validate before clean writes. No response aliases are assumed from the retired API. Re-enable only after adapter, timestamp/session, pagination, idempotency, scope, no-data and no-partial-write tests pass.

Master integration belongs in `src/ingest/master/` with dedicated verified provider adapters/mappings. Preserve operator-controlled statuses; do not infer master lists from price history or auto-sync during ingest. Streaming belongs in `src/ingest/streaming/` with a separately verified protocol and authentication contract; historical offline payload decoders are not evidence of v3 protocol compatibility. Restore schedules only in a separately reviewed capability implementation.

For a future SSI v4: add a client under `src/providers/ssi/clients/`, an adapter satisfying `DataSourceAdapter.fetch()` / `AdapterResult` under `adapters/`, a versioned `src/contracts/mappings/ssi_v4.json`, and per-dataset registry entries. Supply raw-source identity in adapter results, verify semantics and fixture parity, then mark only verified datasets ready. Business services must not select endpoint versions or silently fall back. V4 is not implemented here.

## Operational documentation / Tài liệu vận hành

- [English CLI runbook](CLI_USAGE.md)
- [Hướng dẫn CLI tiếng Việt](CLI_USAGE.vi.md)
- [Documentation audit](CLI_DOCUMENTATION_AUDIT.md)
- [Báo cáo kiểm tra tài liệu](CLI_DOCUMENTATION_AUDIT.vi.md)
