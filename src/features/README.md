# src/features

[Tiếng Việt](README.vi.md)

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
## Foreign EOD features and rankings

Foreign V2 uses only same-symbol `stock_daily` rows ordered by trading date, with observed-row windows; it neither reads nor infers a calendar file. Missing foreign values remain missing. It writes only `stock_foreign_features_daily`, never repairs source rows. Historical corrections can affect following windows; review reported affected dates. See [Foreign EOD specification](../../docs/FOREIGN_EOD_FEATURES.md).

Preview (`--symbol`, `--date`, optional `--show-source`/`--json`) and check (`--from`, `--to`, optional `--symbols`) are READ-ONLY — database read. Daily and backfill are WRITE — feature calculation unless `--dry-run`, which calculates/validates without persistence. Daily requires a date and accepts `--mode target|incremental` (target default); backfill requires both dates. Omitted symbols use active database scope. `--calendar-file` remains a deprecated ignored parser option, not a prerequisite.

`foreign-rank` and `foreign-symbol` are READ-ONLY — database RPC (`get_foreign_ranking`, `get_foreign_symbol_history`). Rank requires date/ranking; ranking is attention, accumulation, distribution or emerging. Window is 1/5/20 (default 5), sort value/ratio (default value); optional market, symbols, top (20), offset (0). History requires one symbol/date, lookback defaults 20. RPC/schema must exist separately; zero CLI exit does not certify nonempty/fresh results. Inspect row quality, coverage and source freshness before interpreting rankings.

```bash
python main.py foreign-features-preview --symbol SSI --date 19/10/2026 --show-source
python main.py foreign-features-daily --date 19/10/2026 --symbols SSI HPG --dry-run
python main.py foreign-features-daily --date 19/10/2026 --symbols SSI --mode target
python main.py foreign-features-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI --dry-run
python main.py foreign-features-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py foreign-features-check --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py foreign-rank --date 19/10/2026 --ranking attention --window 1 --symbols SSI HPG --top 20
python main.py foreign-rank --date 19/10/2026 --ranking accumulation --window 5 --sort value --symbols SSI HPG --top 20
python main.py foreign-rank --date 19/10/2026 --ranking distribution --window 20 --sort ratio --top 20
python main.py foreign-rank --date 19/10/2026 --ranking emerging --window 5 --sort value --top 20
python main.py foreign-symbol --symbol SSI --date 19/10/2026 --lookback 20
```
## Index features

The separate index feature domain reads `index_daily` and persists `index_features_daily` keyed by `(index_code,trading_date)`. It requires database access only; no SSI requests. Preview and check are READ-ONLY — database read. Daily and backfill are WRITE — feature calculation. Preview/daily require `--date`; backfill/check require `--from` and `--to` (no long date aliases here). Optional `--indexes` accepts space-separated master codes; omitted selects active master rows. Up to 250 prior clean sessions supply warm-up. No source OHLC or missing session is synthesized; insufficient windows retain nulls. Inspect raw-without-clean and missing-feature dates before rerunning an exact scope.

```bash
python main.py index-features-preview --date 19/10/2026 --indexes VNINDEX
python main.py index-features-daily --date 19/10/2026 --indexes VNINDEX HNXINDEX
python main.py index-features-backfill --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX HNXINDEX
python main.py index-features-check --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX
```

[CLI](../../docs/CLI_USAGE.md)
