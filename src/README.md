# Application source

Python package containing SSI integration, persistence, validation, pipelines, and research engines.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Package map

| Path | Responsibility |
| --- | --- |
| `config.py` | Environment-based application configuration. |
| `intraday_value.py` | Shared estimated intraday value calculation. |
| [`ssi/`](ssi/README.md) | SSI REST and streaming access. |
| [`database/`](database/README.md) | Supabase reads and writes. |
| [`validation/`](validation/README.md) | Raw/clean record validation. |
| [`pipeline/`](pipeline/README.md) | Production orchestration and ingest flows. |
| [`engine/`](engine/README.md) | Feature computation and downstream research engines. |

## Dependency direction

```text
SSI clients → pipelines → validation/database
clean database data → feature engine → optional research signal/backtest code
```

Ingest must not call the feature, signal, or backtest engines automatically. Downstream research code must not repair or overwrite source data.

## Data contracts

- `stock_daily` supplies `1d` features.
- `stock_intraday` persists clean `1m` candles only.
- Higher intraday timeframes are aggregated in the feature engine.
- Intraday `value` is currently estimated as `round(close * volume)` and remains `NULL` when inputs are invalid or missing.
- Missing SSI data is not fabricated or silently replaced with zero.

## Development

Keep changes scoped, preserve public functions and schema contracts, handle API/database errors explicitly, and add migrations for schema changes. Run targeted tests followed by `python -m pytest -q` when practical.

> Feature execution update (issue #99): implementation is owned by `src/features/`. Use source-isolated `features-daily` and `features-intraday`; `features` and `intraday` are compatibility routes. Intraday persistence uses closed buckets, official daily open, continuous indicators/high-low, same-bucket prior-20-observed-date volume/value baselines, and nullable flags. See `src/features/README.md`.
