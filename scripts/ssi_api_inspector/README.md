# SSI REST API inspector

Read-only CLI for Phase 0 SSI FastConnect Data REST verification. It sends direct HTTP requests, prints the raw SSI response envelope, and never writes Supabase or any database.

## Requirements

Install project dependencies and set credentials in the existing environment/config:

```bash
SSI_CONSUMER_ID=...
SSI_CONSUMER_SECRET=...
```

The tool redacts consumer credentials, bearer tokens, authorization headers, and nested token-like keys before printing output. Do not share full CLI output blindly; even redacted envelopes can contain market/account context.

## Commands

```bash
python scripts/ssi_api_inspector/inspect.py list
python scripts/ssi_api_inspector/inspect.py run securities --market HOSE --limit 3
python scripts/ssi_api_inspector/inspect.py run daily-stock-price --symbol SSI --date 10/07/2026 --full-json
python scripts/ssi_api_inspector/inspect.py run all --symbol SSI --date 10/07/2026 --index-code VNINDEX --limit 2
```

`--limit` controls the number of sample records printed from the detected list location. `--full-json` prints the complete raw JSON envelope after deep redaction.

## Endpoints

| CLI name | Method | Endpoint | Main params |
| --- | --- | --- | --- |
| `access-token` | POST | `AccessToken` | JSON `consumerID`, `consumerSecret` |
| `securities` | GET | `Securities` | `Market`, `PageIndex`, `PageSize` |
| `securities-details` | GET | `SecuritiesDetails` | `Market`, `Symbol`, `PageIndex`, `PageSize` |
| `index-components` | GET | `IndexComponents` | `IndexCode`, `PageIndex`, `PageSize` |
| `index-list` | GET | `IndexList` | `Exchange`, `PageIndex`, `PageSize` |
| `daily-ohlc` | GET | `DailyOhlc` | `Symbol`, `FromDate`, `ToDate`, `PageIndex`, `PageSize`, `ascending` |
| `intraday-ohlc` | GET | `IntradayOhlc` | `Symbol`, `FromDate`, `ToDate`, `resolution=1`, `PageIndex`, `PageSize`, `ascending` |
| `daily-index` | GET | `DailyIndex` | `IndexCode`, `FromDate`, `ToDate`, `PageIndex`, `PageSize` |
| `daily-stock-price` | GET | `DailyStockPrice` | `Symbol`, `FromDate`, `ToDate`, `Market`, `PageIndex`, `PageSize` |

In the current Trading T+ architecture, `DailyStockPrice` is the canonical daily source for T+/swing research. `DailyOhlc` is inspected for cross-checking only. Foreign trading is derived from fields in `DailyStockPrice`; there is no standalone public REST `ForeignTrading` endpoint in this task. Orderbook/market depth is not part of the public REST endpoint list for this inspector; use the separate streaming/snapshot utilities for supported quote messages.
