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

### Intraday gaps, returns, and indicators

- Feature aggregation uses observed `stock_intraday` 1m candles only. A 5m/15m/60m bucket is emitted when it has at least one observed candle; an entirely empty bucket is not fabricated. OHLC uses first/max/min/last and volume/value sum only observed candles, without crossing a Vietnam trading date or lunch break.
- `return_1m`, `return_5m`, and `return_15m` are wall-clock/time-aware. At row time `t`, the reference is the latest candle at or before `t - horizon`, on the same Vietnam trading date and in the same morning/afternoon session. The backward tolerance is one minute for the 1m horizon and two minutes for the 5m/15m horizons. Missing or stale references produce null; future candles, overnight rows, unlimited forward-fill, and zero returns are never used.
- Applicable columns remain unchanged: 1m has all three returns; 5m has 5m/15m; 15m has 15m; 60m has none; 1d returns remain null.
- EMA9/20/50, RSI14, MACD, volume/value MA20, and high/low 20 bars remain **bar-based**. For example, EMA20 on 1m is the EMA of 20 observed 1m candles; no-trade minutes can make those 20 candles span more than 20 wall-clock minutes. This intentionally differs from the time-aware returns.
- Intraday VWAP remains cumulative observed candle value divided by cumulative observed candle volume. Intraday value is the normalized estimate `round(close * volume)`, not exact SSI exchange turnover; no volume/value is invented for empty minutes.

Historical intraday feature rows calculated with row-based `pct_change(n)` require a feature-only backfill after this rule change. Raw and clean data do not require reingest.

## Signal and backtest status

Signal and backtest modules are downstream research/MVP code in Phase 0. They must be invoked separately, must not repair source data, and must not be presented as validated profitability evidence.
The MVP intraday backtest selects only a feature row at or before signal time and rejects an entry older than its explicit two-minute default staleness limit; it never selects the nearest future row.

## Testing

```bash
python -m pytest -q tests/features/test_feature_engine.py
python -m pytest -q tests/legacy/test_backtest_engine.py
```

When a feature formula changes, document the old/new formula, affected timeframes, historical-row impact, backfill need, and tests.
