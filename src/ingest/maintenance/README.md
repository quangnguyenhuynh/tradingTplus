# src/ingest/maintenance

## Guarded operator intraday backfill

`stock-intraday-backfill` (compatible alias `backfill-intraday`) now runs the existing guarded manual pilot sequentially for an explicit inclusive range and explicit symbols. Default is **DRY_RUN**; only `--write` persists. `--dry-run`/`--write` are mutually exclusive. Dates accept DD/MM/YYYY or YYYY-MM-DD and keep --from-date/--to-date aliases. No ALL/wildcards/comma scopes, implicit universe, future/inverted ranges or force overwrite. Normalize/deduplicate symbols in input order; process dates ascending and symbols in that order. Reject more than **50 symbol/weekday pairs** before services. Weekends skip without calls; a weekend-only range is an OK no-op.

```bash
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI HPG --data-source ssi_v3 --dry-run
# Owner only, after reviewing the dry-run/preflight:
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI HPG --data-source ssi_v3 --write
```

Each pair reuses `run_manual_intraday()` eligibility (both persisted statuses active), SSI v3 whole-day pagination/mapping/value validation, exact Vietnam-day UTC conflict preflight, raw-first insert-only persistence and scoped readback. No SSI v2, timestamp repair, value estimate, batch filtering or conflicting overwrite. Preserve raw source JSON/hash and exact BIGINT `ohlc.value`; completeness stays UNVERIFIED, with no 226-bar requirement. A valid empty source is NO_SOURCE_DATA, not a verified holiday or success. Unsupported historical dates and invalid batches remain explicit failures. Dry-run performs zero mutations/partition RPCs and reports actual inserts=0 with separate planned counts; absent DB preflight is BLOCKED, never write-ready.

Ordinary pair conflicts/source validation errors continue safely; systemic configuration/auth/exhausted shared-dependency errors halt with completed and unprocessed scopes reported. No automatic retry of ambiguous DB writes. Pair PARTIAL retains raw commits, acknowledged counts and recovery; inspect exact scope read-only, resolve the cause, then explicitly rerun. Identical rows skip and missing clean can be completed under the existing guards; no cleanup/delete or cross-table atomicity claim. Range OK requires every planned pair verified (or no work); mixed verified success/failure is PARTIAL; no verified success with failures is FAILED, even when a pair committed partial raw data. Per-pair PARTIAL/insert counts remain visible in that FAILED range. CLI exits 0 only for OK, 1 for any non-success/unverified range, 2 for invalid scope/source/arguments. Other CLI exits are unchanged.

Range JSON retains `flow=backfill-intraday`, reports planned/processed/OK/blocked/partial/failed/no-source pairs, totals, planned inserts, halted/unprocessed scopes and full pilot summaries in per_symbol_date. Only summaries survive each pair; raw/clean working batches are released. Registry remains preview with no generic intraday production factory. Single-symbol/day stock-intraday is unchanged; intraday-ingest, combined backfill, refill, master and streaming stay disabled. No automatic feature/completeness/signal/backtest/alert stage. Workflow stock-intraday remains disabled and unscheduled. No migration or development backfill; Codex performs no live writes. See [runbook](../../../docs/backfill/README.md) for operator recovery and post-write read-only checks.

Canonical CLI names and compatible legacy aliases (no removal date): `stock-daily-backfill` → `backfill-daily`; `stock-intraday-backfill` → `backfill-intraday`. Compatible CLI spellings remain; daily/index behavior is unchanged. Intraday uses the guarded operator range contract. Stock Daily/Index Daily backfill are ACTIVE / WRITE; Stock Intraday backfill is guarded operator-only, DRY_RUN by default, with explicit --write and at most 50 weekday pairs; unattended routes remain disabled.

[Tiếng Việt](README.vi.md)

## Stock Daily historical backfill

WRITE — raw/clean ingest: `stock-daily-backfill` requires `--from` and `--to`; `--from-date` and `--to-date` are aliases. Optional symbols apply to every included date; omitted means active master scope per ingest. Optional `--data-source ssi_v3` makes selection explicit; omission selects the ready v3 adapter, not the literal value `auto`.

The runner skips weekends, rejects future/reversed ranges, records per-day OK/PARTIAL/FAILED and continues across failures. Weekend-only ranges are OK no-ops. It does not verify completeness: inspect daily summaries and perform a separately scoped read-only check. Reruns may update existing clean rows and retain raw evidence. It does not calculate features or call the disabled combined backfill.

```bash
python main.py stock-daily-backfill --help
python main.py stock-daily-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI HPG --data-source ssi_v3
```
## Temporarily disabled commands

The command groups below retain their parsers but fail before loading handlers or constructing SSI/DB clients. They return exit 1 and JSON status FAILED, error_type NOT_IMPLEMENTED. A rejected explicit source can instead return exit 2 in source preflight. Help still describes previous purposes; it is not evidence of availability.

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
