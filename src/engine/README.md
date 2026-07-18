# Data and research engines

Deterministic feature computation plus downstream signal/backtest research code.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Main files

| File | Current role |
| --- | --- |
| `feature_engine.py` | Loads clean data, aggregates timeframes, runs calculations, and persists `features`. |
| `feature_calculator.py` | Indicator and feature formulas. |
| `data_quality.py` | Data-quality checks used by engine workflows. |
| `signal_engine.py` | Rule-based signal MVP/research engine. |
| `backtest_engine.py` | Backtest MVP/research engine. |
| [`signal/`](signal/README.md) | Reusable signal-rule classes. |

## Feature contract

- Feature execution is explicit and separate from ingest.
- `1d` uses `stock_daily`.
- `1m` uses `stock_intraday`.
- `5m`, `15m`, and `60m` are aggregated from `1m` during feature computation.
- Results remain in one `features` table keyed by `(symbol, timeframe, time)`.
- Incremental runs must load sufficient warm-up history.
- Full and incremental outputs should match on overlapping rows within documented tolerance.
- Calculations must be symbol-isolated, timeframe-aware, rerunnable, backfillable, and free of look-ahead leakage.

## Signal and backtest status

Signal and backtest modules are downstream research/MVP code in Phase 0. They must be invoked separately, must not repair source data, and must not be presented as validated profitability evidence.

## Testing

```bash
python -m pytest -q tests/test_feature_engine.py
python -m pytest -q tests/test_backtest_engine.py
```

When a feature formula changes, document the old/new formula, affected timeframes, historical-row impact, backfill need, and tests.
