# Feature tests

Offline tests for deterministic daily and intraday feature contracts.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Files

| File | Coverage |
| --- | --- |
| `test_feature_engine.py` | Daily/intraday source ownership, aggregation, closed buckets, indicators, baselines, nullable context, persistence, and compatibility routing. |
| `test_feature_range_backfill.py` | Inclusive range validation, warm-up windows, output scoping, and daily/intraday backfill execution. |
| `test_feature_timeframe_policy.py` | Persisted `1d`, `15m`, and `60m` policy and rejection of `1m`/`5m` feature writes. |
| `test_issue99_contract.py` | Regression contracts for isolated symbols, continuous calculations, timestamp semantics, and schema/migration alignment. |

The tests preserve the Phase 0 boundaries: `1d` reads `stock_daily`; intraday
features aggregate clean `stock_intraday` 1-minute candles without writing
higher-timeframe source candles; ingest does not run features; feature execution
does not run signals or backtests.

## Run

```bash
python -m pytest -q tests/features
```

Tests use fakes/mocks and do not write production data.
