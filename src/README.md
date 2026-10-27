# src — architecture and operations

[Tiếng Việt](README.vi.md)

`main.py → src/cli → src/ingest` orchestrates ingestion. `src/providers/ssi` selects v3 clients/adapters; `src/contracts` maps/validates contracts and `src/quality` checks quality. `src/database` keeps raw/clean persistence separate. `src/features/{stock,foreign,index}` independently reads clean data; `src/research/{screener,analogs}` is downstream research. Ingestion never starts features or research automatically.

| Domain | Responsibility |
| --- | --- |
| [cli](cli/README.md) | Parse / preflight / dispatch |
| [providers/ssi](providers/ssi/README.md) | SSI v3 clients, adapters, readiness registry |
| [contracts](contracts/README.md) | Canonical mappings and validation |
| [ingest](ingest/README.md) | Stock/index source orchestration, raw/clean persistence |
| [quality](quality/README.md) | Validators and completeness |
| [features/stock](features/stock/README.md) | stock_daily → 1d; clean 1m → 15m/60m |
| [features/foreign](features/foreign/README.md) | stock_daily → stock_foreign_features_daily |
| [features/index](features/index/README.md) | index_daily → index_features_daily |
| [research/screener](research/screener/README.md) | V1/V2 preview and explicit apply |
| [research/analogs](research/analogs/README.md) | Same-symbol EOD snapshots/outcomes/research |

Verified against `dev` commit `b5cb3276` (PR #178). Run from the repository root. Examples use illustrative dates and symbols; check source availability and choose the exact intended scope before executing. Syntax was checked offline, not against live SSI or Supabase.

SSI v3 Stock Daily (`securitiesSummary`) and Index Daily (`indexSummary`) ingestion are ACTIVE. Stock, foreign and index features are ACTIVE on persisted clean data. Screener and Historical Analog are RESEARCH_ACTIVE. Master sync has guarded orchestration with symbols/securities guarded READY, index datasets BLOCKED; streaming and orderbook capture remain NOT_IMPLEMENTED. The retired source has no fallback.

READ-ONLY — database read means no writes but still requires database access. READ-ONLY — SSI API request can make live requests without using Supabase. WRITE labels identify persistence, including explicit apply and scoped replacement. UNSUPPORTED means an input or operation is rejected, not an empty successful result.
```bash
python main.py stock-eod 19/10/2026 --symbols SSI --data-source ssi_v3
python main.py features-daily --date 19/10/2026 --symbols SSI
python main.py features-intraday --date 19/10/2026 --symbols SSI --timeframes 15m 60m
```

[CLI](../docs/CLI_USAGE.md) · [Scripts](../scripts/README.md)
