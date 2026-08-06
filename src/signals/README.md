# Signals

Daily setup creates candidates, not signals. The scanner uses closed feature candles at or before its cutoff; only an approved exact strategy version/config may be persisted live.

### Operational Phase 1 CLI (2026-08-06)
The database-backed commands are executable and remain separate from ingest/features. Dry-run is the default; `--write` is explicit. Production setup/signal writes require the exact approved strategy version/config. Historical sessions come from observed `stock_daily`; live setup requires an explicit target session. First-match uniqueness permits only one signal per strategy/config/symbol/session. Rule/evaluator changes require a new version and new evidence.
