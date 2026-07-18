# Validation tests

Focused tests for the validation package.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Files

- `test_daily_validator.py`: daily required fields, OHLC, limits, volume/value, and date rules.
- `test_intraday_validator.py`: candle and intraday-batch validation.
- `test_streaming_validator.py`: streaming payload/mapping validation.

## Command

```bash
python -m pytest -q tests/validation
```

## Test design

- Cover valid, invalid, missing, malformed, and boundary values.
- Keep tests deterministic and independent of live SSI/Supabase services.
- Assert validation status and issue details, not only a boolean result.
- Add regression tests for every production data-quality bug.
- Do not weaken a rule merely to accept an unexplained source anomaly; retain and document evidence first.
