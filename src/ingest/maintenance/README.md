# src/ingest/maintenance

## Canonical EOD CLI — 28 October 2026

| Command | Existing behavior retained |
| --- | --- |
| `stock-eod` | Stock ingest + existing daily completeness; active-symbol filtering |
| `stock-eod-backfill` | Inclusive stock daily backfill; no added completeness |
| `index-eod` | Existing index daily raw/clean ingest |
| `index-eod-backfill` | Existing inclusive index daily backfill |

Only these four top-level names are supported for stock/index EOD ingest/backfill.
Removed (no aliases/redirects): `daily`, `stock-daily`, `stock-daily-backfill`,
`backfill-daily`, `index-daily`, `index-daily-backfill`, `index-backfill`.
Old direct daily had different date/scope/completeness semantics and is retired;
stock-eod retains run_stock_eod_pipeline rather than adopting daily_run behavior.
Stock/index EOD defaults resolve the latest weekday on/before today in Vietnam;
original date validation, scope rules, summaries and exit codes remain unchanged.
Backfill date aliases --from/--from-date and --to/--to-date remain available.
PARTIAL can still exit 0 under existing _status_to_exit; no exit-policy changes.
Internal daily_run/run_daily_ingest/run_index_daily_ingest/backfill imports,
stock_daily/index_daily dataset IDs and JSON flows (including index-daily,
backfill-daily/index-backfill) remain unchanged. Inspector `stock-daily` remains.
Stock/index pipelines stay separate; no automatic feature/signal/backtest.
No migration/schema/data changes or required backfill. Do not execute WRITE
examples to verify naming. Historical naming/alias reports below are superseded.

```bash
python main.py stock-eod --help
python main.py stock-eod-backfill --help
python main.py index-eod --help
python main.py index-eod-backfill --help
```


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

Canonical EOD backfills: `stock-eod-backfill`, `index-eod-backfill`; old EOD aliases are removed. Intraday alone retains `stock-intraday-backfill` / `backfill-intraday`. Existing runner behavior is unchanged.

[Tiếng Việt](README.vi.md)

## Stock Daily historical backfill

WRITE — raw/clean ingest: `stock-eod-backfill` requires `--from` and `--to`; `--from-date` and `--to-date` are aliases. Optional symbols apply to every included date; omitted means active master scope per ingest. Optional `--data-source ssi_v3` makes selection explicit; omission selects the ready v3 adapter, not the literal value `auto`.

The runner skips weekends, rejects future/reversed ranges, records per-day OK/PARTIAL/FAILED and continues across failures. Weekend-only ranges are OK no-ops. It does not verify completeness: inspect daily summaries and perform a separately scoped read-only check. Reruns may update existing clean rows and retain raw evidence. It does not calculate features or call the disabled combined backfill.

```bash
python main.py stock-eod-backfill --help
python main.py stock-eod-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI HPG --data-source ssi_v3
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
