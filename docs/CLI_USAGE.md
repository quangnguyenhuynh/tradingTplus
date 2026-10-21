# Production CLI

Run from the repository root. `python main.py COMMAND --help` preserves the existing argument definitions. Exit codes: 0 for supported OK/PARTIAL, 1 for FAILED/unavailable, 2 for invalid arguments or unsupported source.

| Capability | Status |
| --- | --- |
| SSI v3 Stock Daily / Index Daily | ACTIVE |
| SSI v3 Stock Intraday ingestion | NOT_IMPLEMENTED |
| SSI v3 Master Data synchronization | NOT_IMPLEMENTED |
| SSI v3 Streaming / Orderbook | NOT_IMPLEMENTED |
| Stock technical, foreign and index features | ACTIVE |
| Historical Analog / Screener V1/V2 | RESEARCH_ACTIVE |
| SSI v2 REST / legacy SignalR connection | RETIRED |

## Setup and commands

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --help
python main.py stock-eod --help
python main.py index-daily --help
python main.py features-intraday --help
```

Daily ingest requires `SSI_API_KEY`, `SSI_API_SECRET`, `SUPABASE_URL` and a server-side Supabase key (`SUPABASE_SERVICE_KEY`, or the existing key configuration). Features/research need database configuration only. See `.env.example`; never commit credentials.

Active source commands: `daily`, `stock-eod` / `stock-daily`, `backfill-daily`, `index-daily`, `index-backfill`, `index-preview`, `index-check`. Only `ssi_v3` is accepted as a REST source. Invalid/retired sources return exit 2 before API/database access.

Unavailable commands preserve their parsers: `init`, `sync-master-data`, `intraday-ingest`, `stock-intraday`, `backfill-intraday`, `backfill`, `refill`, `streaming-ingest`. They return exit 1 and JSON `status=FAILED`, `error_type=NOT_IMPLEMENTED`, with no API/DB access. Combined backfill/refill never execute just the daily portion.

Features remain explicit: `features`, `features-daily`, `features-intraday`, foreign/index feature commands. Persisted stock feature timeframes remain `1d`, `15m`, `60m`; daily uses `stock_daily`, intraday aggregates historical clean `stock_intraday` 1m without writing aggregated candles back. Screener and Historical Analog remain research workflows.

## Common examples

```bash
python main.py stock-eod 19/10/2026 --symbols SSI --data-source ssi_v3
python main.py backfill-daily --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py index-preview --date 2026-10-19 --indexes VNINDEX --json
python main.py features-daily --date 19/10/2026 --symbols SSI
python main.py features-intraday --date 19/10/2026 --symbols SSI --timeframes 15m 60m
python main.py foreign-features-preview --symbol SSI --date 19/10/2026 --show-source
python main.py stock-screener --help
python main.py analogs --help
```

Choose an explicit intended symbol/date scope before executing commands that write. These examples were not run against production. The inspector is read-only:

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-daily --symbol SSI --date 2026-10-19 --data-source ssi_v3
```

Native v3 endpoint inspection may inspect preview datasets; this does not enable production intraday/master ingestion. `ssi_v2` is rejected, including in the inspector. Streaming inspector/capture and combined diagnostics now return unavailable JSON without connection attempts.

## Command inventory

- `sync-master-data` — NOT_IMPLEMENTED
- `init` — NOT_IMPLEMENTED
- `daily` — supported; see `--help`
- `index-daily` — supported; see `--help`
- `index-backfill` — supported; see `--help`
- `index-check` — supported; see `--help`
- `index-preview` — supported; see `--help`
- `index-features-preview` — supported; see `--help`
- `index-features-daily` — supported; see `--help`
- `index-features-backfill` — supported; see `--help`
- `index-features-check` — supported; see `--help`
- `foreign-features-preview` — supported; see `--help`
- `foreign-features-daily` — supported; see `--help`
- `foreign-features-backfill` — supported; see `--help`
- `foreign-features-check` — supported; see `--help`
- `foreign-rank` — supported; see `--help`
- `foreign-symbol` — supported; see `--help`
- `intraday-ingest` — NOT_IMPLEMENTED
- `stock-eod` — supported; see `--help`
- `stock-daily` — supported; see `--help`
- `stock-intraday` — NOT_IMPLEMENTED
- `backfill-daily` — supported; see `--help`
- `backfill-intraday` — NOT_IMPLEMENTED
- `backfill` — NOT_IMPLEMENTED
- `refill` — NOT_IMPLEMENTED
- `features` — supported; see `--help`
- `features-daily` — supported; see `--help`
- `features-intraday` — supported; see `--help`
- `stock-screener` — supported; see `--help`
- `stock-screener-config` — supported; see `--help`
- `streaming-ingest` — NOT_IMPLEMENTED
- `analogs` — supported; see `--help`

No schema, RPC, conflict-key, migration or production-data changes are part of this restructuring. Historical raw/clean/master/streaming/features and source provenance remain untouched. No migration or backfill is required. Ingest never starts features or research automatically.

See [Foreign EOD details](FOREIGN_EOD_FEATURES.md), [Analog contract](phase1/HISTORICAL_ANALOG_SPEC.md), [Data conventions](DATA_CONVENTIONS.md).
