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
| [`engine/`](engine/README.md) | Legacy manual data-quality utility; no signal/backtest implementation. |
| [`utils/`](utils/README.md) | Shared timezone-aware Vietnam market-time helpers. |

## Dependency direction

```text
SSI clients → pipelines → validation/database
clean database data → explicit feature pipelines
```

Ingest must not call feature computation automatically. Feature execution has no automatic signal/backtest stage; those legacy implementations were removed pending a later redesign.

## Data contracts

- `stock_daily` supplies `1d` features.
- `stock_intraday` persists clean `1m` candles only.
- Higher intraday timeframes are aggregated in the feature engine.
- Intraday `value` is currently estimated as `round(close * volume)` and remains `NULL` when inputs are invalid or missing.
- Missing SSI data is not fabricated or silently replaced with zero.

## Development

Keep changes scoped, preserve public functions and schema contracts, handle API/database errors explicitly, and add migrations for schema changes. Run targeted tests followed by `python -m pytest -q` when practical.
