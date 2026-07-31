# Legacy engine utilities

This package now contains only `data_quality.py`, a manual legacy quality/recompute utility. Deterministic feature calculation is owned by [`src/features/`](../features/README.md).

The legacy signal strategies, disabled signal entrypoint, and MVP backtest engine were removed during Phase 0 because they depended on obsolete feature contracts. There is no executable signal or backtest path. Both layers will receive new contracts in a later, explicit design phase after data and features are verified.

Ingest does not calculate features automatically, and feature execution does not trigger any downstream research stage.

```bash
python -m pytest -q tests/features
```
