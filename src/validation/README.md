# Data validation

Validation models and rules for daily, intraday, and streaming records.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Files

- `models.py`: validation result/status structures.
- `daily_validator.py`: required fields, dates, OHLC, limits, volume/value, and daily consistency rules.
- `intraday_validator.py`: candle-level and batch-level intraday checks.
- `streaming_validator.py`: streaming payload and mapped-row checks.
- `logging_utils.py`: consistent validation logging helpers.
- `__init__.py`: package exports.

## Principles

- Validate before clean-data persistence where the pipeline contract requires it.
- Preserve raw evidence and report suspicious source values instead of silently correcting them.
- Reject or quarantine invalid timestamps; never replace them with the current time.
- Preserve `NULL` for unknown fields unless a verified rule defines another value.
- Daily reference, ceiling, and floor prices are optional context. Dependent checks run only when their inputs exist. A coherent OHLC range wholly on one side of the supplied limits is retained as a corporate-action warning; isolated limit violations and invalid OHLC remain blocking.
- Check OHLC relationships, finite values, non-negative volume/value, valid symbol/date, duplicates, sessions, and batch consistency where applicable.
- Completeness depends on symbol, trading date, source, timeframe, and session; one universal candle count is not sufficient.

## Testing

```bash
python -m pytest -q tests/validation
```

Add a focused test for every new validation rule, including valid, invalid, missing, and boundary cases.
