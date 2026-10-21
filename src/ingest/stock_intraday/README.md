# src/ingest/stock_intraday

[Tiếng Việt](README.vi.md)

## Temporarily disabled commands

The eight commands below retain their parsers but fail before loading handlers or constructing SSI/DB clients. They return exit 1 and JSON status FAILED, error_type NOT_IMPLEMENTED. A rejected explicit source can instead return exit 2 in source preflight. Help still describes previous purposes; it is not evidence of availability.

| Command | Previous purpose | Required future adapter / dataset |
| --- | --- | --- |
| sync-master-data, init | Idempotent master sync | Verified v3 master adapters preserving operator status; master |
| intraday-ingest | Source 1m raw/clean ingestion | Verified v3 1m adapter, pagination, timestamps, units; stock_intraday |
| stock-intraday | 1m ingestion and completeness | Same adapter; stock_intraday |
| backfill-intraday | Source 1m history | Same adapter; stock_intraday |
| backfill | Combined daily/intraday plus checks | Same adapter; stock_intraday; no partial daily work |
| refill | Single-symbol source/check/features | Same adapter; stock_intraday; no partial daily/features work |
| streaming-ingest | Bounded streaming, optional write | Verified v3 protocol/auth/capture adapter; streaming |

Orderbook capture is likewise disabled pending a verified streaming adapter; do not invent a public REST depth endpoint. Historical raw/clean/master/feature/streaming rows remain stored and usable under their contracts. No fallback, deletion or historical repair occurs from calling a disabled command. Below are help commands only, not production success examples.

```bash
python main.py init --help
python main.py sync-master-data --help
python main.py intraday-ingest --help
python main.py stock-intraday --help
python main.py backfill-intraday --help
python main.py backfill --help
python main.py refill --help
python main.py streaming-ingest --help
```
## Stock technical features

All three routes are WRITE — feature calculation into `stock_features`, keyed by `(symbol,timeframe,time)`. No SSI credentials are needed. `1d` reads `stock_daily`; `15m` and `60m` aggregate existing clean 1m `stock_intraday` in memory with daily price context. Only closed buckets are persisted. `stock_intraday` continues to store only 1m. Unsupported feature persistence: `1m`, `5m`. Disabled source ingestion does not disable calculation over previously persisted intraday history.

`features` is the compatibility router: optional `--date`, `--mode incremental|full` (incremental default), optional symbols, default timeframes `15m 60m 1d`; it has no range or replace option. `features-daily` always selects 1d. `features-intraday` defaults to `15m 60m` and supports `--as-of` as Vietnam `HH:MM` or a timezone-aware timestamp. Do not combine as-of with a range. Explicit source-isolated routes require a target date, a complete range, or full mode.

Incremental uses per-stream watermarks and bounded warm-up (daily five years; intraday 250 observed sessions, not calendar days). A valid no-output incremental run may be an OK no-op. A range runs inclusive backfill. Full recomputes and upserts selected history without deletion and can consume substantial memory; it cannot combine with a date/range. Source corrections do not automatically invalidate old feature history.

**Potentially destructive WRITE — explicit rebuild:** replace and rebuild-clean are equivalent atomic scoped replacements. Require exactly one symbol, one persisted timeframe, and both range bounds; no wildcard/ALL, no `--date`. Compute and validate a non-empty replacement first, then call the existing service-role RPC to delete and rewrite exactly that scope. Confirm complete source/warm-up, inspect a source sample and retain before/after evidence before executing. These routes have no dry-run flag. Intraday replacement must explicitly choose one timeframe; the default two are rejected.

```bash
python main.py features --help
python main.py features-daily --help
python main.py features-intraday --help
python main.py features --date 19/10/2026 --symbols SSI HPG --timeframes 1d
python main.py features-daily --date 19/10/2026 --symbols SSI
python main.py features-daily --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py features-daily --mode full --symbols SSI
python main.py features-intraday --date 19/10/2026 --symbols SSI --timeframes 15m 60m --as-of 14:30
python main.py features-intraday --from 01/10/2026 --to 19/10/2026 --symbols SSI --timeframes 60m
python main.py features-daily --mode replace --symbols SSI --from 01/10/2026 --to 19/10/2026
python main.py features-intraday --mode rebuild-clean --symbols SSI --timeframes 15m --from 01/10/2026 --to 19/10/2026
```

[CLI](../../../docs/CLI_USAGE.md)
