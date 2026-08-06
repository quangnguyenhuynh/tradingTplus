# Legacy engine utilities

This package contains `data_quality.py`, a manual legacy quality/recompute
utility. Deterministic feature calculation belongs to
[`src/features/`](../features/README.md).

Fixed-rule strategy, signal, and backtest implementations now live in their own
packages; they were not removed. They are dormant/superseded and must not be
treated as the accepted Phase 1 production path. The target design is
[`docs/phase1/HISTORICAL_ANALOG_SPEC.md`](../../docs/phase1/HISTORICAL_ANALOG_SPEC.md).

Ingest does not calculate features automatically, and features do not trigger
downstream research.

```bash
python -m pytest -q tests/features
```
