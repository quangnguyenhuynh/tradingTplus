# src/ingest/index_daily

[Tiếng Việt](README.vi.md)

## Index Daily preview and ingestion

`index-preview` is READ-ONLY — SSI API request; it never reads or writes DB rows. Required: either `--date` or `--from` together with `--to`, and comma-separated `--indexes`. Default output is a normalized table; `--raw` displays raw JSON, `--json` normalized JSON; these flags are mutually exclusive. No production `--data-source` option exists here.

`index-daily` is WRITE — raw/clean ingest from SSI v3 `indexSummary` into `index_raw_daily`, then validated `index_daily`. Optional positional date defaults to the latest weekday on/before today in Vietnam. `--indexes` takes one or more space-separated values. Omitted indexes select active `index_master`; explicit values must exist in master (explicit selection can include inactive rows). Empty master or unknown code raises ValueError, normally CLI exit 2. The error text suggests sync-master-data, but that command is disabled: inspect the persisted master and resolve it in separately authorized maintenance. Preview remains available without master data.

```bash
python main.py index-preview --help
python main.py index-daily --help
python main.py index-preview --date 2026-10-19 --indexes VNINDEX --raw
python main.py index-preview --from 2026-10-01 --to 2026-10-19 --indexes VNINDEX,HNXINDEX --json
python main.py index-daily 19/10/2026 --indexes VNINDEX HNXINDEX --data-source ssi_v3
python main.py index-daily 19/10/2026
```
## Index Daily backfill and completeness

`index-backfill` is WRITE — raw/clean ingest, with required inclusive `--from`/`--to` (aliases `--from-date`/`--to-date`), optional master-backed `--indexes`, and optional source. It skips weekends and reports day/index counts; no feature calculation follows automatically.

`index-check` is READ-ONLY — database read of raw/clean coverage for an optional positional date and master-backed indexes. The default is the previous weekday, not the index-daily default. It needs database credentials only. Raw persistence is not proof that a valid clean row exists. An OK/PARTIAL ingest return must be followed by review of validation/completeness evidence.

```bash
python main.py index-backfill --help
python main.py index-check --help
python main.py index-backfill --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX HNXINDEX
python main.py index-check 19/10/2026 --indexes VNINDEX
```

[CLI](../../../docs/CLI_USAGE.md)
