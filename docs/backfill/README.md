# Production source-data backfill

## Architecture

TradingTPlus exposes three independent Phase 0 range pipelines:

```text
run_daily_backfill_pipeline()    -> daily ingest for every eligible date
run_intraday_backfill_pipeline() -> 1m intraday ingest for every eligible date
run_backfill_pipeline()          -> complete daily branch -> complete intraday branch
                                  -> completeness check for every eligible date
```

None runs features, signals, or backtests. Weekday holidays are not guessed: SSI empty responses and missing data remain observable, with no fabricated rows or silent zero replacement.

## Commands

```bash
python main.py backfill-daily --from 01/07/2026 --to 10/07/2026 --symbols SSI HPG
python main.py backfill-intraday --from 01/07/2026 --to 10/07/2026 --symbols SSI HPG
python main.py backfill --from 01/07/2026 --to 10/07/2026 --symbols SSI HPG
```

`--from-date` and `--to-date` are aliases. Ranges use `DD/MM/YYYY`, include both endpoints, reject future/reversed ranges, run dates sequentially, and skip/report Saturdays and Sundays. A weekend-only range is an `OK` no-op.

Explicit symbols are stripped, uppercased, and deduplicated in first-seen order once before processing; an empty explicit scope is invalid. Omission uses current master symbols.

## Branch behavior and data impact

- **`backfill-daily`** runs only historical daily ingest. It preserves daily index synchronization and index daily ingest, so an intentional run may write `raw_daily`, `stock_daily`, `index_daily`, and existing index master/context tables. `--symbols` scopes stock ingest only. It does not run intraday ingest or completeness.
- **`backfill-intraday`** runs only historical SSI 1m intraday ingest and may write `raw_intraday` and `stock_intraday` with only `timeframe='1m'`. It reads existing `stock_daily` context when available; missing context remains visible as `PARTIAL`. It never runs daily ingest or completeness automatically.
- **`backfill`** runs the complete daily branch before the complete intraday branch, then reads source tables through scoped completeness checking for each eligible date. It retains both branch summaries and creates combined `backfill-day` summaries using EOD-compatible status rules. It does not call EOD directly.

Each branch records a date-level exception and continues later dates. Combined completeness exceptions are also recorded without discarding branch results. Range status is `OK` when every processed date is `OK`, `FAILED` when every date failed, and `PARTIAL` for mixed statuses or any partial date. Exit codes are `0` for `OK`/`PARTIAL`, `1` for `FAILED`/runtime failure, and `2` for invalid arguments.

No production backfill runs automatically after deployment, and no historical rerun is required solely because these commands are deployed. Run only an explicitly authorized date/symbol repair scope.

## Compatibility

`backfill(...)` remains deprecated, accepts legacy ISO dates, rejects `allow_future=True`, and delegates to `run_backfill_pipeline()`. `scripts/backfill_sample.py` remains a deprecated delegate to the combined command.

## Tests

```bash
python -m pytest -q tests/pipeline/test_backfill_pipeline.py
python -m pytest -q tests/cli/test_cli_refactor.py
python -m pytest -q tests/pipeline/test_eod_pipeline.py
python -m pytest -q
```
