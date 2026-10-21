# src/features/foreign

[Tiếng Việt](README.vi.md)

## Foreign EOD features and rankings

Foreign V2 uses only same-symbol `stock_daily` rows ordered by trading date, with observed-row windows; it neither reads nor infers a calendar file. Missing foreign values remain missing. It writes only `stock_foreign_features_daily`, never repairs source rows. Historical corrections can affect following windows; review reported affected dates. See [Foreign EOD specification](../../../docs/FOREIGN_EOD_FEATURES.md).

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

[CLI](../../../docs/CLI_USAGE.md)
