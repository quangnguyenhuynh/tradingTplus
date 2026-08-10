# Legacy engine utilities

This package contains `data_quality.py`, a manual legacy quality/recompute
utility. Deterministic feature calculation belongs to
[`src/features/`](../features/README.md).

The retired rule-based strategy, signal, and backtest packages have been removed.
The active Phase 1 contract is
[`docs/phase1/HISTORICAL_ANALOG_SPEC.md`](../../docs/phase1/HISTORICAL_ANALOG_SPEC.md).

Ingest does not calculate features automatically, and features do not trigger
downstream research.

```bash
python -m pytest -q tests/features
```
