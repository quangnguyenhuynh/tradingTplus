# src/ingest/index_daily

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


Canonical EOD backfills: `stock-eod-backfill`, `index-eod-backfill`; old EOD aliases are removed. Intraday alone retains `stock-intraday-backfill` / `backfill-intraday`. Existing runner behavior is unchanged.

[Tiếng Việt](README.vi.md)

## Index Daily preview and ingestion

`index-preview` is READ-ONLY — SSI API request; it never reads or writes DB rows. Required: either `--date` or `--from` together with `--to`, and comma-separated `--indexes`. Default output is a normalized table; `--raw` displays raw JSON, `--json` normalized JSON; these flags are mutually exclusive. No production `--data-source` option exists here.

`index-eod` is WRITE — raw/clean ingest from SSI v3 `indexSummary` into `index_raw_daily`, then validated `index_daily`. Optional positional date defaults to the latest weekday on/before today in Vietnam. `--indexes` takes one or more space-separated values. Omitted indexes select active `index_master`; explicit values must exist in master (explicit selection can include inactive rows). Empty master or unknown code raises ValueError, normally CLI exit 2. The error text suggests sync-master-data, but that command is disabled: inspect the persisted master and resolve it in separately authorized maintenance. Preview remains available without master data.

```bash
python main.py index-preview --help
python main.py index-eod --help
python main.py index-preview --date 2026-10-19 --indexes VNINDEX --raw
python main.py index-preview --from 2026-10-01 --to 2026-10-19 --indexes VNINDEX,HNXINDEX --json
python main.py index-eod 19/10/2026 --indexes VNINDEX HNXINDEX --data-source ssi_v3
python main.py index-eod 19/10/2026
```
## Index Daily backfill and completeness

`index-eod-backfill` is WRITE — raw/clean ingest, with required inclusive `--from`/`--to` (aliases `--from-date`/`--to-date`), optional master-backed `--indexes`, and optional source. It skips weekends and reports day/index counts; no feature calculation follows automatically.

`index-check` is READ-ONLY — database read of raw/clean coverage for an optional positional date and master-backed indexes. The default is the previous weekday, not the index-daily default. It needs database credentials only. Raw persistence is not proof that a valid clean row exists. An OK/PARTIAL ingest return must be followed by review of validation/completeness evidence.

```bash
python main.py index-eod-backfill --help
python main.py index-check --help
python main.py index-eod-backfill --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX HNXINDEX
python main.py index-check 19/10/2026 --indexes VNINDEX
```

[CLI](../../../docs/CLI_USAGE.md)
