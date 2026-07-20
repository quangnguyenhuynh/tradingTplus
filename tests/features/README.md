# Feature tests

Tests for deterministic feature calculation and timeframe-aware persistence.

Coverage includes 1-minute source loading, 5m/15m/60m aggregation, `stock_daily`-based 1d features, warm-up history, pagination, target-date filtering, no-look-ahead breakout logic, per-session resets, and the single `features` table contract.

```bash
python -m pytest -q tests/features
```
