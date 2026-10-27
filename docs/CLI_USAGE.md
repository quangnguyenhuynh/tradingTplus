# TradingTPlus CLI — Quick guide

[Tiếng Việt](CLI_USAGE.vi.md) · [Full reference](CLI_REFERENCE.md) · [Home](../README.md)

Run from the **repository root** with Python 3.11 and configured SSI/Supabase credentials. Dates below are examples only. **READ** calls API/DB without writing; **WRITE** persists data; **DRY-RUN** checks without writing. Each step is independent: ingestion never automatically runs features, research, signals or backtests.

## Choose a task

| Task | CLI | Effect |
| --- | --- | --- |
| Inspect SSI stock data | `scripts/inspectors/ssi_rest/inspect.py run stock-daily` | READ SSI |
| Stock EOD / backfill | `stock-eod` / `stock-daily-backfill` | WRITE raw/clean |
| Index preview / EOD / backfill | `index-preview` / `index-daily` / `index-daily-backfill` | READ / WRITE |
| Manual intraday 1m / backfill | `stock-intraday` / `stock-intraday-backfill` | DRY-RUN by default; `--write` persists |
| Daily / intraday stock features | `features-daily` / `features-intraday` | WRITE features |
| Index features | `index-features-daily` | WRITE features |
| Foreign feature preview / compute / ranking | `foreign-features-preview` / `foreign-features-daily` / `foreign-rank` | READ / WRITE / READ |
| Stock screener | `stock-screener` | READ by default |

## 1. Inspect before writing — READ

```bash
python scripts/inspectors/ssi_rest/inspect.py run stock-daily --symbol SSI --date 19/10/2026 --show-mapping
python main.py index-preview --date 19/10/2026 --indexes VNINDEX --json
```

## 2. Ingest EOD — WRITE raw/clean

Master records must already exist: `init` and `sync-master-data` have a guarded entrypoint but symbols/securities are guarded READY; index datasets remain BLOCKED. Omit `--data-source` to use the ready SSI v3 default; do not pass `auto`.

```bash
python main.py stock-eod 19/10/2026 --symbols SSI HPG
python main.py stock-daily-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI HPG
python main.py index-daily 19/10/2026 --indexes VNINDEX
python main.py index-daily-backfill --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX
```

The `daily` route differs from `stock-eod` in date defaults and completeness; see the [reference](CLI_REFERENCE.md).

## 3. Manual intraday 1m — DRY-RUN first

Operator-only. One symbol/date per `stock-intraday` call. Range backfill requires explicit dates and symbols, is limited to **50 symbol × weekday pairs**, and never runs unattended. Completeness is unverified; never assume a fixed 226-bar standard.

```bash
# No DB writes
python main.py stock-intraday 20/10/2026 --symbols SSI
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI --dry-run

# Owner only, after successful preflight review
python main.py stock-intraday 20/10/2026 --symbols SSI --write
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI --write
```

For partial writes or conflicts inspect exactly scoped raw/clean before retry; see the [recovery runbook](backfill/README.md).

## 4. Compute features — independent WRITE step

Daily 1d features read `stock_daily`. Intraday 15m/60m features aggregate stored clean 1m. Ingest success alone does not prove completeness.

```bash
python main.py features-daily --date 19/10/2026 --symbols SSI
python main.py features-daily --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py features-intraday --date 19/10/2026 --symbols SSI --timeframes 15m 60m
python main.py index-features-daily --date 19/10/2026 --indexes VNINDEX
```

`--mode replace` and `--mode rebuild-clean` delete/replace scoped features and are intentionally excluded from quick-start examples. See the [reference](CLI_REFERENCE.md).

## 5. Foreign and research

```bash
# READ
python main.py foreign-features-preview --symbol SSI --date 19/10/2026 --show-source
python main.py foreign-rank --date 19/10/2026 --ranking accumulation --window 5 --top 20

# DRY-RUN, then WRITE
python main.py foreign-features-daily --date 19/10/2026 --symbols SSI --dry-run
python main.py foreign-features-daily --date 19/10/2026 --symbols SSI

# READ by default
python main.py stock-screener --date 19/10/2026 --symbols SSI --version v2
```

Historical Analog is gated research and does not automatically emit signals, alerts, or NAV allocations. See [Analog docs](../src/research/analogs/README.md).

## 6. Help and safeguards

```bash
python main.py --help
python main.py stock-eod --help
python main.py features-daily --help
python main.py stock-intraday-backfill --help
```

- Most examples use `DD/MM/YYYY`; supported formats differ by domain. Separate stock symbols with spaces; **`index-preview` alone uses comma-separated index values**.
- Exit code 0 does **not** guarantee full, valid or fresh data. Check counts, status, warnings, raw/clean and completeness. Review PARTIAL/BLOCKED/EMPTY.
- `intraday-ingest`, combined `backfill`, `refill`, and `streaming-ingest` are **UNAVAILABLE**, even if help parses.
- Compatible aliases `backfill-daily`, `backfill-intraday`, `index-backfill` remain accepted; this guide uses canonical names.

[Full CLI/reference](CLI_REFERENCE.md) · [Intraday runbook](STOCK_INTRADAY_PIPELINE.md) · [Backfill](backfill/README.md) · [Scripts](../scripts/README.md) · [Data conventions](DATA_CONVENTIONS.md).

## Master sync — updated 27 October 2026

`sync-master-data` and alias `init` now use guarded orchestration, default DRY_RUN. SSI v3 symbols/securities now support guarded refresh across HOSE/HNX/UPCOM; index_master/index_components remain BLOCKED. READY is scoped to guarded non-destructive refresh; authoritative market completeness remains UNVERIFIED. --write requires one explicit --dataset and a READY provider. Operator statuses are preserved; new stocks/indexes inactive. No migration or price backfill. [Runbook and validation report](../src/ingest/master/README.md).

## Unified master cutover — 27 October 2026

This supersedes earlier independent symbols/securities procedures: symbols is the sole physical write target; securities is a deprecated CLI alias with an explicit warning. all syncs symbols once. Apply Stage A expansion/merge BEFORE application deployment; Stage B retirement is separately owner-approved and aborts by default. Never apply production migrations through the agent. VN50 GROWTH exact index exclusion is counted; HNX-request DERIVATIVES/Future retains its actual domain and inactive defaults. Index capabilities remain BLOCKED. No price backfill. [Runbook](../src/ingest/master/README.md).
