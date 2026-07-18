# Test suite

Offline unit, contract, regression, CLI, migration-text, and pipeline tests.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)
- Validation tests: [`validation/README.md`](validation/README.md)

## Coverage areas

- Production CLI contracts and exit behavior.
- Daily, intraday-ingest, EOD, one-day, and streaming pipelines.
- SSI REST and streaming inspectors.
- Raw/clean mappings and intraday value semantics.
- Feature engine aggregation, incremental/full behavior, and target dates.
- Signal/backtest MVP behavior where currently covered.
- Migration/schema contract text checks.
- Daily, intraday, and streaming validation.

## Commands

```bash
python -m pytest -q tests/test_feature_engine.py
python -m pytest -q tests/test_cli_refactor.py tests/test_eod_pipeline.py
python -m pytest -q tests/validation
python -m pytest -q
python -m compileall main.py src scripts
```

## Rules

- Run the smallest relevant test set first, then the full suite when practical.
- Tests should not require real SSI or Supabase credentials unless clearly marked as integration/smoke tests.
- Mock external API and database calls in unit tests.
- Never write production data from a normal test.
- A docs-only change should still validate paths, commands, and links against the current repository.
- Separate pre-existing failures from failures introduced by the task.

GitHub Actions runs the full pytest suite on pull requests and pushes to `dev`.
