# src/cli — parsing and dispatch

Canonical CLI names and compatible legacy aliases (no removal date): `stock-daily-backfill` → `backfill-daily`; `stock-intraday-backfill` → `backfill-intraday`; `index-daily-backfill` → `index-backfill`. Only CLI naming changes; runners, arguments, JSON flow identifiers and exits stay unchanged. Stock Daily/Index Daily backfill are ACTIVE / WRITE; Stock Intraday backfill is DISABLED / NOT_IMPLEMENTED, separate from the manual pilot.

[Tiếng Việt](README.vi.md)


## Guarded manual intraday pilot

`stock-intraday` now supports exactly one explicit symbol and Vietnam trading date. Default/`--dry-run` is READ-ONLY; only `--write` authorizes the guarded raw → clean insert sequence. SSI credentials are needed; Supabase service credentials enable read-only eligibility/conflict preflight and are required for writes. Without DB configuration, dry-run reports `NOT_RUN_NO_CREDENTIALS`, unknown planned counts and `write_ready=false`.

```bash
python main.py stock-intraday 20/10/2026 --symbols SSI
python main.py stock-intraday 20/10/2026 --symbols SSI --write
```

The second command is **owner-only after reviewing dry-run/preflight**. No ranges, ALL/wildcards, omitted scope, multiple symbols or future dates. Both persisted master statuses must be active. Source is only `ssi_v3`, timeframe only `1m`; canonical value is exact `ohlc.value`, with missing/invalid values blocking this pilot and no estimation fallback. Identical existing rows are skipped; differing canonical clean rows or raw key/source/payload conflicts block. No force overwrite. Raw is confirmed before clean; a partial/ambiguous write exits nonzero and requires scoped inspection then a safe rerun. Cross-table atomicity is not promised. Completeness remains UNVERIFIED. Other intraday ingest/backfill/refill/streaming commands and the schedule remain disabled. Features/signals/backtests never run from this pilot.

See [runbook](../../docs/STOCK_INTRADAY_PIPELINE.md) for sequence, idempotency, partition behavior, recovery and owner verification. The inspector remains entirely read-only; registry readiness remains preview, with no generic production factory.

`parser.py` defines arguments; `__init__.py` parses and performs source/capability preflight before loading a domain handler. Help never executes services. `stock`, `index`, `features`, `foreign`, `screener`, `analogs`, `maintenance` and `streaming` dispatch independently without embedding formulas or enabling disabled sources. `common.py` prints summaries and maps FAILED to exit 1; ValueError becomes 2, while PARTIAL can exit 0.

The seven commands below retain their parsers but fail before loading handlers or constructing SSI/DB clients. They return exit 1 and JSON status FAILED, error_type NOT_IMPLEMENTED. A rejected explicit source can instead return exit 2 in source preflight. Help still describes previous purposes; it is not evidence of availability.

| Command | Previous purpose | Required future adapter / dataset |
| --- | --- | --- |
| sync-master-data, init | Idempotent master sync | Verified v3 master adapters preserving operator status; master |
| intraday-ingest | Source 1m raw/clean ingestion | Verified v3 1m adapter, pagination, timestamps, units; stock_intraday |
| stock-intraday-backfill | Source 1m history | Same adapter; stock_intraday |
| backfill | Combined daily/intraday plus checks | Same adapter; stock_intraday; no partial daily work |
| refill | Single-symbol source/check/features | Same adapter; stock_intraday; no partial daily/features work |
| streaming-ingest | Bounded streaming, optional write | Verified v3 protocol/auth/capture adapter; streaming |

Orderbook capture is likewise disabled pending a verified streaming adapter; do not invent a public REST depth endpoint. Historical raw/clean/master/feature/streaming rows remain stored and usable under their contracts. No fallback, deletion or historical repair occurs from calling a disabled command. Below are help commands only, not production success examples.

```bash
python main.py --help
python main.py features-daily --help
python main.py stock-eod 19/10/2026 --symbols SSI
python main.py foreign-rank --date 19/10/2026 --ranking emerging --window 5 --top 20
```

[All commands, parameters, aliases, defaults and examples](../../docs/CLI_USAGE.md)
