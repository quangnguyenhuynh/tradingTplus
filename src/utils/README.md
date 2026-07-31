# Shared utilities

Small cross-package helpers that do not own ingest, persistence, validation, or
feature orchestration.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Files and contract

- `time_utils.py` defines the `Asia/Ho_Chi_Minh` market timezone, returns
  timezone-aware current market time, and parses source timestamps without
  replacing invalid values with the current time.
- `__init__.py` marks this directory as a Python package.

Callers must keep timestamps timezone-aware. Session logic may convert a UTC
timestamp to Vietnam time, but must never manually add seven hours or substitute
audit timestamps for source candle time.

This package performs no network calls and no database reads or writes.

## Checks

```bash
python -m compileall src/utils
python -m pytest -q tests/validation tests/features
```
