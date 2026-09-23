# Foreign EOD Feature V2

This independent derived pipeline reads only `stock_daily`. Windows are the last 5/10/20 rows of the same symbol ordered by `trading_date`; no calendar is read or inferred. See [`docs/FOREIGN_EOD_FEATURES.md`](../../docs/FOREIGN_EOD_FEATURES.md) for formulas, quality, CLI, migration, and rollout.
