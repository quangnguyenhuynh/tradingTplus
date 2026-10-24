# src/ingest/stock_intraday

Canonical CLI names and compatible legacy aliases (no removal date): `stock-intraday-backfill` → `backfill-intraday`. Only CLI naming changes; runners, arguments, JSON flow identifiers and exits stay unchanged. Stock Daily/Index Daily backfill are ACTIVE / WRITE; Stock Intraday backfill is DISABLED / NOT_IMPLEMENTED, separate from the manual pilot.

[Tiếng Việt](README.vi.md)


## Guarded manual intraday pilot

`stock-intraday` now supports exactly one explicit symbol and Vietnam trading date. Default/`--dry-run` is READ-ONLY; only `--write` authorizes the guarded raw → clean insert sequence. SSI credentials are needed; Supabase service credentials enable read-only eligibility/conflict preflight and are required for writes. Without DB configuration, dry-run reports `NOT_RUN_NO_CREDENTIALS`, unknown planned counts and `write_ready=false`.

```bash
python main.py stock-intraday 20/10/2026 --symbols SSI
python main.py stock-intraday 20/10/2026 --symbols SSI --write
```

The second command is **owner-only after reviewing dry-run/preflight**. No ranges, ALL/wildcards, omitted scope, multiple symbols or future dates. Both persisted master statuses must be active. Source is only `ssi_v3`, timeframe only `1m`; canonical value is exact `ohlc.value`, with missing/invalid values blocking this pilot and no estimation fallback. Identical existing rows are skipped; differing canonical clean rows or raw key/source/payload conflicts block. No force overwrite. Raw is confirmed before clean; a partial/ambiguous write exits nonzero and requires scoped inspection then a safe rerun. Cross-table atomicity is not promised. Completeness remains UNVERIFIED. Other intraday ingest/backfill/refill/streaming commands and the schedule remain disabled. Features/signals/backtests never run from this pilot.

See [runbook](../../../docs/STOCK_INTRADAY_PIPELINE.md) for sequence, idempotency, partition behavior, recovery and owner verification. The inspector remains entirely read-only; registry readiness remains preview, with no generic production factory.

## Temporarily disabled commands

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
python main.py init --help
python main.py sync-master-data --help
python main.py intraday-ingest --help
python main.py stock-intraday --help
python main.py stock-intraday-backfill --help
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

## Multi-page SSI v3 intraday preview (read-only)

The REST inspector stock-intraday/native intraday-ohlc routes now use the shared preview adapter and download successive pages from the requested start until explicit termination or failure/bound. `--limit` limits display only; `--full-json` includes every received raw page and clean candidate. `--max-pages` defaults to 100 (1–1000); hitting the bound, repeated pages, inconsistent totals or request failures return FAILED/exit 1 and retain received evidence. Other daily/index/catalog inspector routes keep their single-page behavior.

Owner-provided live SSI excerpts for 2026-10-20 verify `ohlc.tradingDate` in `YYYY/MM/DD HH:mm:ss`, source `ohlc.value`, and terminal `{"code":204,"msg":"No Content"}`. This exact source-local timestamp is explicitly interpreted in `Asia/Ho_Chi_Minh` and normalized to UTC; valid explicit-offset forms remain supported. The legacy `time` alias still requires an explicit timezone. Date-only/time-only and arbitrary naive formats remain rejected; no request-date fabrication or minute shifting.

Canonical v3 `value` is **SSI-reported intraday candle value**, parsed exactly as a nonnegative signed-BIGINT integer without float conversion. There is **no calculated estimate or fallback**. Absent/null/empty source value stays NULL with SOURCE_VALUE_MISSING; malformed/non-finite/fractional/negative/overflow value rejects the candidate. Zero stays zero. Source-value presence, numeric validity and preservation are reported separately from independently verified market-data semantics (still false).

The verified 204/No Content envelope terminates OHLC 1m paging only without conflicting payload/error markers and after metadata/count checks. Its original envelope is retained and termination is provider_no_content_204. Short nonempty pages never terminate by themselves; repeats, wrong totals, malformed/errors and page-limit truncation still fail. --limit controls display only; --full-json retains received raw pages, candidates and diagnostics.

The supplied day had 226 unique rows over 23 nonempty pages then page 24, descending order, 135 morning/90 afternoon/one 14:45 candle. These are owner-reported observations for that day, not a universal count or a formula rule. Only two real candle objects and the terminal envelope were supplied; offline replay verifies those 2/2 without reconstructing missing rows. Agent live rerun: NOT_RUN (no credentials). Bar-start/end, independent value/turnover semantics and market completeness remain unverified. Unattended ingestion/scheduling remains disabled; the inspector preview performs zero database reads/writes. The isolated manual pilot is described above.

See the [runbook and promotion checklist](../../../docs/STOCK_INTRADAY_PIPELINE.md) for field mappings, paging, validation/session/gap rules, source limitations and separate promotion steps.

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --from-date 2026-10-01 --to-date 2026-10-19 --page-size 100 --max-pages 100 --limit 5
python scripts/inspectors/ssi_rest/inspect.py run intraday-ohlc --symbol SSI --date 2026-10-19 --ascending --limit 5
```

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --page-size 10 --max-pages 100 --limit 5
```
