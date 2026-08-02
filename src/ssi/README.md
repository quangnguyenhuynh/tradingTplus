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
- Pagination uses an order-independent hash of every returned page, retains all
  previously seen hashes, and raises `SSIPaginationError` for a repeated page or
  cycle of any length. A short page is not EOF. Only a trustworthy exact
  `totalRecord`, an empty page, or an exact caller limit terminates normally.
- `SSI_MAX_PAGES_PER_REQUEST` is the named default safety bound (10,000 pages).
  Callers may lower it per request; reaching it is an error, never partial
  success. Invalid/changing totals and rows beyond a declared total are errors.
- Streaming tools must use explicit symbols/channels, bounded timeout/message counts, and read-only defaults.

## Evidence boundary

An external review of SSI FastConnect Data Specs v2.2 documents
`DailyStockPrice` at `/api/v2/Market/DailyStockPrice`, comparison-only
`DailyOhlc`, and resolution `1` for `IntradayOhlc`. This repository records that
as `DOCUMENTED_FROM_EXTERNAL_PDF_REVIEW`; it does not claim that the runtime
agent opened the attachment. The document does not establish reliable live
pagination, universal intraday-volume semantics, or exact intraday turnover.
Those remain separate read-only live-validation questions.

Verify unfamiliar payloads with the dedicated read-only inspectors before modifying ingest mappings.
