# src/cli — parsing and dispatch

[Tiếng Việt](README.vi.md)

`parser.py` defines arguments; `__init__.py` parses and performs source/capability preflight before loading a domain handler. Help never executes services. `stock`, `index`, `features`, `foreign`, `screener`, `analogs`, `maintenance` and `streaming` dispatch independently without embedding formulas or enabling disabled sources. `common.py` prints summaries and maps FAILED to exit 1; ValueError becomes 2, while PARTIAL can exit 0.

The eight commands below retain their parsers but fail before loading handlers or constructing SSI/DB clients. They return exit 1 and JSON status FAILED, error_type NOT_IMPLEMENTED. A rejected explicit source can instead return exit 2 in source preflight. Help still describes previous purposes; it is not evidence of availability.

| Command | Previous purpose | Required future adapter / dataset |
| --- | --- | --- |
| sync-master-data, init | Idempotent master sync | Verified v3 master adapters preserving operator status; master |
| intraday-ingest | Source 1m raw/clean ingestion | Verified v3 1m adapter, pagination, timestamps, units; stock_intraday |
| stock-intraday | 1m ingestion and completeness | Same adapter; stock_intraday |
| backfill-intraday | Source 1m history | Same adapter; stock_intraday |
| backfill | Combined daily/intraday plus checks | Same adapter; stock_intraday; no partial daily work |
| refill | Single-symbol source/check/features | Same adapter; stock_intraday; no partial daily/features work |
| streaming-ingest | Bounded streaming, optional write | Verified v3 protocol/auth/capture adapter; streaming |

Orderbook capture is likewise disabled pending a verified streaming adapter; do not invent a public REST depth endpoint. Historical raw/clean/master/feature/streaming rows remain stored and usable under their contracts. No fallback, deletion or historical repair occurs from calling a disabled command. Below are help commands only, not production success examples.

```bash
python main.py --help
python main.py features-daily --help
python main.py stock-eod 19/10/2026 --symbols SSI
python main.py foreign-rank --date 19/10/2026 --ranking emerging --window 5 --top 20
```

[All commands, parameters, aliases, defaults and examples](../../docs/CLI_USAGE.md)
