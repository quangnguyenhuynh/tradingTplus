# Legacy and research tests

Tests for code that remains in the repository for compatibility or research but is not yet validated production T+ behavior.

`test_backtest_engine.py` covers the current bar-based MVP. It does not prove correct T+3/T+5 trading-session execution and must not be treated as profitability evidence.

```bash
python -m pytest -q tests/legacy
```
