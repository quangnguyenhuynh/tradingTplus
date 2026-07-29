# Downstream research engines

This package contains signal/backtest research code and a legacy data-quality
utility. Deterministic feature calculation is owned by
[`src/features/`](../features/README.md).

## Files

| Path | Current role |
| --- | --- |
| `signal_engine.py` | Disabled legacy signal entrypoint; fails fast because its old rules require removed feature columns. |
| [`signal/`](signal/README.md) | Legacy rule classes retained for later redesign; not wired into production. |
| `backtest_engine.py` | Backtest MVP/research engine, invoked separately. |
| `data_quality.py` | Legacy manual quality/recompute utility; not part of the production ingest or feature CLI. |

The removed `feature_engine.py` and `feature_calculator.py` compatibility shims
must not be recreated. Import feature APIs from `src.features`, or use the
source-specific modules:

```python
from src.features.daily import run_daily_features_with_summary
from src.features.intraday import run_intraday_features_with_summary
```

Signal and backtest code is downstream of validated features. It must run
separately, must not repair source data, and must not be treated as validated
profitability evidence during Phase 0.

## Tests

```bash
python -m pytest -q tests/features
python -m pytest -q tests/legacy/test_backtest_engine.py
```
