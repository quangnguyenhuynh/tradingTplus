# Test suite

Offline unit, contract, regression, CLI, migration-text, validation, and pipeline tests for Trading T+.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Structure

| Directory | Responsibility |
| --- | --- |
| [`ingest/`](ingest/README.md) | Daily/intraday mapping, value calculation, payload reuse, ingest orchestration, and completeness queries. |
| [`features/`](features/README.md) | Feature formulas, timeframe aggregation, incremental/full execution, and persistence contracts. |
| [`validation/`](validation/README.md) | Daily, intraday, and streaming validation rules. |
| [`streaming/`](streaming/README.md) | Streaming ingest behavior and migration contract tests. |
| [`inspectors/`](inspectors/README.md) | Read-only SSI REST and streaming inspector tests. |
| [`pipeline/`](pipeline/README.md) | EOD orchestration and dry-run behavior. |
| [`cli/`](cli/README.md) | Production CLI and script-entrypoint contracts. |

`conftest.py` adds the repository root to `sys.path` so tests remain import-stable after being grouped into subdirectories.

## Common commands

```bash
python -m pytest -q tests/ingest
python -m pytest -q tests/features
python -m pytest -q tests/validation
python -m pytest -q tests/streaming tests/inspectors
python -m pytest -q tests/pipeline tests/cli
python -m pytest -q
python -m compileall main.py src scripts tests
```

## Rules

- Run the smallest relevant group first, then the full suite when practical.
- Normal tests must not require live SSI or Supabase credentials.
- Mock external API and database access.
- Tests must not write production data.
- Every production data-quality bug should receive a deterministic regression test.
- Do not weaken validation merely to accept an unexplained source anomaly.
- Do not add signal/backtest tests until a later explicit contract-design phase.
- Phase 0 validation tests also assert numeric tolerance, mismatch/unknown classification, historical payload NULL policy, schema catalog contracts, and absence of write/RPC calls.

GitHub Actions runs the complete pytest suite for pull requests and pushes to `dev`.
