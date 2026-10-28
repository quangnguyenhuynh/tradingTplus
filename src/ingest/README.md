# src/ingest

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

## Stock Daily ingestion

**Historical / đã nghỉ:** `daily` is WRITE — raw/clean ingest only. It fetches SSI v3 `securitiesSummary`, retains source payload/hash in `stock_raw_daily`, validates and persists canonical `stock_daily`. It does not run completeness or downstream calculations. No date means the latest weekday strictly before today in Vietnam. Explicit symbols are used directly; omitted symbols load active persisted master symbols. Removed top-level command; use stock-eod with its existing active scope and completeness.

`stock-eod` is WRITE — raw/clean ingest plus daily-only completeness. They intersect explicit symbols with active master symbols and report ignored unknown/inactive values. Empty active scope returns FAILED. Their default date is the latest weekday on or before today in Vietnam, unlike `daily`. Completeness checks the current run timing and expected source. Neither route ingests indexes/intraday, writes a separate foreign-trading dataset, or starts features. Deprecated intraday counts/summary do not indicate an intraday operation.

Explicit weekend/future source-write dates are rejected. An empty holiday response is reported; rows are never synthesized. Both SSI and Supabase credentials are required.

```bash
python main.py stock-eod --help
python main.py stock-eod --help
python main.py stock-eod --help
python main.py stock-eod 19/10/2026 --symbols SSI
python main.py stock-eod 19/10/2026 --symbols SSI HPG --data-source ssi_v3
python main.py stock-eod --symbols SSI
python main.py stock-eod --symbols SSI
python main.py stock-eod 19/10/2026 --symbols SSI HPG
```
## Stock Daily historical backfill

WRITE — raw/clean ingest: `stock-eod-backfill` requires `--from` and `--to`; `--from-date` and `--to-date` are aliases. Optional symbols apply to every included date; omitted means active master scope per ingest. Optional `--data-source ssi_v3` makes selection explicit; omission selects the ready v3 adapter, not the literal value `auto`.

The runner skips weekends, rejects future/reversed ranges, records per-day OK/PARTIAL/FAILED and continues across failures. Weekend-only ranges are OK no-ops. It does not verify completeness: inspect daily summaries and perform a separately scoped read-only check. Reruns may update existing clean rows and retain raw evidence. It does not calculate features or call the disabled combined backfill.

```bash
python main.py stock-eod-backfill --help
python main.py stock-eod-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI HPG --data-source ssi_v3
```
## Index Daily preview and ingestion

`index-preview` is READ-ONLY — SSI API request; it never reads or writes DB rows. Required: either `--date` or `--from` together with `--to`, and comma-separated `--indexes`. Default output is a normalized table; `--raw` displays raw JSON, `--json` normalized JSON; these flags are mutually exclusive. No production `--data-source` option exists here.

`index-eod` is WRITE — raw/clean ingest from SSI v3 `indexSummary` into `index_raw_daily`, then validated `index_daily`. Optional positional date defaults to the latest weekday on/before today in Vietnam. `--indexes` takes one or more space-separated values. Omitted indexes select active `index_master`; explicit values must exist in master (explicit selection can include inactive rows). Empty master or unknown code raises ValueError, normally CLI exit 2. The error text suggests sync-master-data, but its SSI v3 datasets remain BLOCKED: inspect the persisted master and resolve it in separately authorized maintenance. Preview remains available without master data.

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
## Temporarily disabled commands

The command groups below retain their parsers but fail before loading handlers or constructing SSI/DB clients. They return exit 1 and JSON status FAILED, error_type NOT_IMPLEMENTED. A rejected explicit source can instead return exit 2 in source preflight. Help still describes previous purposes; it is not evidence of availability.

| Command | Previous purpose | Required future adapter / dataset |
| --- | --- | --- |
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

[CLI](../../docs/CLI_USAGE.md)

## Master sync — updated 27 October 2026

`sync-master-data` and alias `init` now use guarded orchestration, default DRY_RUN. SSI v3 symbols/securities now support guarded refresh across HOSE/HNX/UPCOM; index_master/index_components remain BLOCKED. READY is scoped to guarded non-destructive refresh; authoritative market completeness remains UNVERIFIED. --write requires one explicit --dataset and a READY provider. Operator statuses are preserved; new stocks/indexes inactive. No migration or price backfill. [Runbook and validation report](master/README.md).
