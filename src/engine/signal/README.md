# Signal rule modules

Reusable rule classes for the current signal research/MVP layer.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Files

- `base.py`: common signal rule interface and shared contracts.
- `trend.py`: trend-oriented rule logic.
- `breakout.py`: breakout-oriented rule logic.
- `reversal.py`: reversal-oriented rule logic.
- `__init__.py`: package exports.

## Boundaries

- Rules consume validated feature rows; they do not fetch SSI data or write raw/clean tables.
- Each matched signal should remain explainable and include the relevant symbol, timeframe, time, type/score, and reason according to the caller's storage contract.
- Contradictory matches must not be silently combined.
- Rule thresholds are not considered optimized or production-validated in Phase 0.
- Do not make 1-minute indicators the primary justification for a T+3/T+5 thesis.

Add or change rules only in an explicit signal task after feature contracts and historical data are validated.
