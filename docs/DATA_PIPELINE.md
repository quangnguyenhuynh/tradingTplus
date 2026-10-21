# Data pipeline

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

## Active ingestion

Stock daily: resolve date and active persisted symbol scope → v3 `securitiesSummary` with existing pagination → preserve exact raw payload/hash/source → canonical mapping → field validation → existing raw/clean persistence. `stock-eod` adds daily completeness only. Daily backfill repeats the daily service over the existing eligible-date rules.

Index daily: resolve persisted active `index_master` scope → v3 `indexSummary` → raw evidence → explicit mapping/validation → existing `index_raw_daily` / `index_daily` writes. No automatic master sync; empty scope reports failure. Preview uses the same v3 adapter without constructing a database client. Index backfill/check remain separate.

## Disabled integrations

Intraday ingest, master sync, streaming/orderbook capture and combined backfill/refill fail before any service construction or partial write. Reusable canonical validators, timestamp/value helpers, scope rules and persistence interfaces remain isolated. Historical records are not rewritten, relabeled or deleted. Retired historical raw mappings cannot be used as active providers; Phase 0 reconciliation reports UNKNOWN when a retired/unknown source cannot be remapped.

## Independent downstream work

Stock `1d` features read `stock_daily`; `15m`/`60m` features aggregate existing clean 1m history using unchanged session and closed-candle rules. Foreign/index features retain their tables and formulas. Explicit incremental/full/target-date/range/scoped-replacement workflows remain available. Research configurations, profile hashes, formulas and DB contracts are preserved.

No schema, RPC, conflict-key, migration or production-data changes are part of this restructuring. Historical raw/clean/master/streaming/features and source provenance remain untouched. No migration or backfill is required. Ingest never starts features or research automatically.

## Future integrations

Implement verified intraday mapping/fetching in `src/providers/ssi/adapters/` and orchestrate it only in `src/ingest/stock_intraday/`. The future input is a separately verified SSI v3 1m response, with explicit units, timestamp/bar conventions, symbol/date identity and raw traceability. The output must satisfy the existing `stock_intraday` canonical contract (`symbol`, aware market `time`, `timeframe='1m'`, nullable typed OHLCV/value and price context); preserve raw payloads, reject invalid timestamps and validate before clean writes. No response aliases are assumed from the retired API. Re-enable only after adapter, timestamp/session, pagination, idempotency, scope, no-data and no-partial-write tests pass.

Master integration belongs in `src/ingest/master/` with dedicated verified provider adapters/mappings. Preserve operator-controlled statuses; do not infer master lists from price history or auto-sync during ingest. Streaming belongs in `src/ingest/streaming/` with a separately verified protocol and authentication contract; historical offline payload decoders are not evidence of v3 protocol compatibility. Restore schedules only in a separately reviewed capability implementation.

For a future SSI v4: add a client under `src/providers/ssi/clients/`, an adapter satisfying `DataSourceAdapter.fetch()` / `AdapterResult` under `adapters/`, a versioned `src/contracts/mappings/ssi_v4.json`, and per-dataset registry entries. Supply raw-source identity in adapter results, verify semantics and fixture parity, then mark only verified datasets ready. Business services must not select endpoint versions or silently fall back. V4 is not implemented here.
