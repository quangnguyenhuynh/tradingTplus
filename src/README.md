# Application source

Python package containing SSI integration, persistence, validation, pipelines, and deterministic features.

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
| [`features/`](features/README.md) | Daily/intraday feature calculation and explicit execution. |
| [`engine/`](engine/README.md) | Legacy manual data-quality utility. |
| [`strategies/`](strategies/README.md) | Dormant fixed-rule research implementation. |
| [`signals/`](signals/README.md) | Dormant daily-setup/intraday-scan research implementation. |
| [`backtest/`](backtest/README.md) | Dormant fixed-rule replay/outcome research implementation. |
| [`utils/`](utils/README.md) | Shared timezone-aware Vietnam market-time helpers. |

## Dependency direction

```text
SSI clients → pipelines → validation/database
clean database data → explicit feature pipelines
```

Ingest must not call feature computation automatically. Feature execution does
not automatically invoke any downstream research stage. Fixed-rule
strategy/signal/backtest code still exists but is dormant and superseded by the
accepted [same-symbol historical-analog design](../docs/phase1/HISTORICAL_ANALOG_SPEC.md),
which is not implemented yet.

## Data contracts

- `stock_daily` supplies `1d` features.
- `stock_intraday` persists clean `1m` candles only.
- Higher intraday timeframes are aggregated in the feature engine.
- Intraday `value` is currently estimated as `round(close * volume)` and remains `NULL` when inputs are invalid or missing.
- Missing SSI data is not fabricated or silently replaced with zero.

## Development

Keep changes scoped, preserve public functions and schema contracts, handle API/database errors explicitly, and add migrations for schema changes. Run targeted tests followed by `python -m pytest -q` when practical.
