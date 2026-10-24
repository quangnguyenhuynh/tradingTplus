# src/ingest/workflows

Canonical CLI names and compatible legacy aliases (no removal date): `stock-intraday-backfill` → `backfill-intraday`. Compatible CLI spellings remain; daily/index behavior is unchanged. Intraday uses the guarded operator range contract. Stock Daily/Index Daily backfill are ACTIVE / WRITE; Stock Intraday backfill is guarded operator-only, DRY_RUN by default, with explicit --write and at most 50 weekday pairs; unattended routes remain disabled.

[Tiếng Việt](README.vi.md)


## Guarded manual intraday pilot

`stock-intraday` now supports exactly one explicit symbol and Vietnam trading date. Default/`--dry-run` is READ-ONLY; only `--write` authorizes the guarded raw → clean insert sequence. SSI credentials are needed; Supabase service credentials enable read-only eligibility/conflict preflight and are required for writes. Without DB configuration, dry-run reports `NOT_RUN_NO_CREDENTIALS`, unknown planned counts and `write_ready=false`.

```bash
python main.py stock-intraday 20/10/2026 --symbols SSI
python main.py stock-intraday 20/10/2026 --symbols SSI --write
```

The second command is **owner-only after reviewing dry-run/preflight**. No ranges, ALL/wildcards, omitted scope, multiple symbols or future dates. Both persisted master statuses must be active. Source is only `ssi_v3`, timeframe only `1m`; canonical value is exact `ohlc.value`, with missing/invalid values blocking this pilot and no estimation fallback. Identical existing rows are skipped; differing canonical clean rows or raw key/source/payload conflicts block. No force overwrite. Raw is confirmed before clean; a partial/ambiguous write exits nonzero and requires scoped inspection then a safe rerun. Cross-table atomicity is not promised. Completeness remains UNVERIFIED. Unattended intraday-ingest, combined backfill, refill, streaming and the schedule remain disabled. Features/signals/backtests never run from this pilot.

See [runbook](../../../docs/STOCK_INTRADAY_PIPELINE.md) for sequence, idempotency, partition behavior, recovery and owner verification. The inspector remains entirely read-only; registry readiness remains preview, with no generic production factory.

## Stock Daily ingestion

`daily` is WRITE — raw/clean ingest only. It fetches SSI v3 `securitiesSummary`, retains source payload/hash in `stock_raw_daily`, validates and persists canonical `stock_daily`. It does not run completeness or downstream calculations. No date means the latest weekday strictly before today in Vietnam. Explicit symbols are used directly; omitted symbols load active persisted master symbols.

`stock-eod` and its exact alias `stock-daily` are WRITE — raw/clean ingest plus daily-only completeness. They intersect explicit symbols with active master symbols and report ignored unknown/inactive values. Empty active scope returns FAILED. Their default date is the latest weekday on or before today in Vietnam, unlike `daily`. Completeness checks the current run timing and expected source. Neither route ingests indexes/intraday, writes a separate foreign-trading dataset, or starts features. Deprecated intraday counts/summary do not indicate an intraday operation.

Explicit weekend/future source-write dates are rejected. An empty holiday response is reported; rows are never synthesized. Both SSI and Supabase credentials are required.

```bash
python main.py daily --help
python main.py stock-eod --help
python main.py stock-daily --help
python main.py daily 19/10/2026 --symbols SSI
python main.py daily 19/10/2026 --symbols SSI HPG --data-source ssi_v3
python main.py daily --symbols SSI
python main.py stock-eod --symbols SSI
python main.py stock-daily 19/10/2026 --symbols SSI HPG
```
## Temporarily disabled commands

The remaining disabled command groups below retain their parsers but fail before loading handlers or constructing SSI/DB clients. They return exit 1 and JSON status FAILED, error_type NOT_IMPLEMENTED. A rejected explicit source can instead return exit 2 in source preflight. Help still describes previous purposes; it is not evidence of availability.

| Command | Previous purpose | Required future adapter / dataset |
| --- | --- | --- |
| sync-master-data, init | Idempotent master sync | Verified v3 master adapters preserving operator status; master |
| intraday-ingest | Source 1m raw/clean ingestion | Verified v3 1m adapter, pagination, timestamps, units; stock_intraday |
| backfill | Combined daily/intraday plus checks | Same adapter; stock_intraday; no partial daily work |
| refill | Single-symbol source/check/features | Same adapter; stock_intraday; no partial daily/features work |
| streaming-ingest | Bounded streaming, optional write | Verified v3 protocol/auth/capture adapter; streaming |

Orderbook capture is likewise disabled pending a verified streaming adapter; do not invent a public REST depth endpoint. Historical raw/clean/master/feature/streaming rows remain stored and usable under their contracts. No fallback, deletion or historical repair occurs from calling a disabled command. Below are help commands only, not production success examples.

```bash
python main.py init --help
python main.py sync-master-data --help
python main.py intraday-ingest --help
python main.py stock-intraday --help
python main.py stock-intraday-backfill --help
python main.py backfill --help
python main.py refill --help
python main.py streaming-ingest --help
```

[CLI](../../../docs/CLI_USAGE.md)
