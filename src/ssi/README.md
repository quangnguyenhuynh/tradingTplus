# SSI integration

Clients for SSI FastConnect Data REST and classic ASP.NET SignalR streaming.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)
- REST inspection: [`../../scripts/ssi_api_inspector/`](../../scripts/ssi_api_inspector/README.md)
- Streaming inspection: [`../../scripts/ssi_streaming_inspector/`](../../scripts/ssi_streaming_inspector/README.md)

## Files

- `api.py`: authentication, REST requests, paging, response extraction, and endpoint-specific helpers.
- `streaming.py`: SignalR negotiation/subscription and bounded message handling.
- `__init__.py`: package exports.

## REST contract

The project uses documented SSI endpoints such as `AccessToken`, `Securities`, `SecuritiesDetails`, `IndexComponents`, `IndexList`, `DailyOhlc`, `IntradayOhlc`, `DailyIndex`, and `DailyStockPrice` where implemented.

- `DailyStockPrice` is the canonical daily source.
- `DailyOhlc` is for cross-checking.
- `IntradayOhlc` is requested at resolution 1 for persisted intraday data.
- Foreign trading is derived from daily-stock-price fields.
- Do not invent public REST orderbook or foreign-trading endpoints.

## Safety and errors

- Read credentials from environment configuration.
- Never log consumer secrets, bearer tokens, or authorization headers.
- Retry authentication only with a bounded policy.
- Handle empty, invalid, and changed response envelopes explicitly.
- Do not fabricate rows when SSI returns no data.
- Streaming tools must use explicit symbols/channels, bounded timeout/message counts, and read-only defaults.

Verify unfamiliar payloads with the dedicated read-only inspectors before modifying ingest mappings.
