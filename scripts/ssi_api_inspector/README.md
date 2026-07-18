# SSI REST API inspector

Read-only CLI for Phase 0 SSI FastConnect Data REST verification.

The inspector sends direct HTTP requests to SSI, prints the real response envelope in a readable form, and never writes to Supabase or any database. Use it to verify endpoint availability, request parameters, paging, empty responses, response keys, record fields, and differences between SSI endpoints before changing the ingest or clean-data pipelines.

## Documentation

- 🇺🇸 English: [README.md](README.md)
- 🇻🇳 Tiếng Việt: [README.vi.md](README.vi.md)

## Scope and safety

- Read-only for database state.
- Does not import `SupabaseClient`.
- Does not insert, update, upsert, or delete data.
- Automatically obtains an SSI access token when an authenticated endpoint is called.
- Retries authentication once when SSI returns HTTP `401`.
- Redacts consumer credentials, bearer tokens, authorization headers, and nested token-like keys before printing output.
- Does not calculate features, signals, or backtest results.

Do not share complete CLI output blindly. Even after token redaction, an SSI response can still contain market, symbol, or account-related context.

## Requirements

Run all commands from the project root.

Activate the project Python environment and install the existing project dependencies. For example:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

The exact environment setup can differ from the examples above. Reuse the project environment when it already exists.

## SSI credentials

The inspector reads the existing project configuration from environment variables. Add the following values to the project `.env` file or export them in the current shell:

```env
SSI_CONSUMER_ID=your_consumer_id
SSI_CONSUMER_SECRET=your_consumer_secret
```

Do not commit real credentials, tokens, or `.env` contents to GitHub.

Supabase credentials are not required because this inspector does not access the database.

## Quick start

List all supported CLI endpoint names:

```bash
python scripts/ssi_api_inspector/inspect.py list
```

Inspect one endpoint:

```bash
python scripts/ssi_api_inspector/inspect.py run daily-stock-price \
  --symbol SSI \
  --market HOSE \
  --date 10/07/2026 \
  --limit 3
```

Inspect all supported data endpoints with the same common arguments:

```bash
python scripts/ssi_api_inspector/inspect.py run all \
  --symbol SSI \
  --market HOSE \
  --exchange HOSE \
  --index-code VNINDEX \
  --date 10/07/2026 \
  --page-size 20 \
  --limit 3
```

`run all` excludes the standalone `access-token` report. The client still obtains a token automatically for authenticated endpoint calls.

## CLI syntax

```text
python scripts/ssi_api_inspector/inspect.py list

python scripts/ssi_api_inspector/inspect.py run <endpoint> [options]
```

Use built-in help to confirm the current CLI contract:

```bash
python scripts/ssi_api_inspector/inspect.py --help
python scripts/ssi_api_inspector/inspect.py run --help
```

## Supported endpoints

| CLI name | HTTP method | SSI endpoint | Main parameters |
| --- | --- | --- | --- |
| `access-token` | POST | `AccessToken` | JSON `consumerID`, `consumerSecret` |
| `securities` | GET | `Securities` | `Market`, `PageIndex`, `PageSize` |
| `securities-details` | GET | `SecuritiesDetails` | `Market`, `Symbol`, `PageIndex`, `PageSize` |
| `index-components` | GET | `IndexComponents` | `IndexCode`, `PageIndex`, `PageSize` |
| `index-list` | GET | `IndexList` | `Exchange`, `PageIndex`, `PageSize` |
| `daily-ohlc` | GET | `DailyOhlc` | `Symbol`, `FromDate`, `ToDate`, paging, optional `ascending=true` |
| `intraday-ohlc` | GET | `IntradayOhlc` | `Symbol`, dates, `resolution=1`, paging, optional `ascending=true` |
| `daily-index` | GET | `DailyIndex` | `IndexCode`, `FromDate`, `ToDate`, paging |
| `daily-stock-price` | GET | `DailyStockPrice` | `Symbol`, dates, `Market`, paging |

For the current Trading T+ architecture:

- `DailyStockPrice` is the canonical daily source for T+/swing research.
- `DailyOhlc` is used for cross-checking only.
- `IntradayOhlc` is requested with `resolution=1` because raw intraday storage is 1-minute data.
- 5-minute, 15-minute, and 60-minute data should be aggregated later in the feature pipeline, not fetched or stored as raw timeframes here.
- Foreign trading fields are inspected from `DailyStockPrice`; the public REST specification used by this project does not define a standalone `ForeignTrading` endpoint.
- Public REST orderbook/market-depth inspection is outside this CLI. Use the separate supported streaming/snapshot utilities.

## Command options

| Option | Default | Description |
| --- | --- | --- |
| `--symbol` | `SSI` | Stock symbol used by symbol-based endpoints. |
| `--date` | `10/07/2026` | Explicit date in `DD/MM/YYYY` format. Used as both `FromDate` and `ToDate`. |
| `--market` | `HOSE` | Market for `securities`, `securities-details`, and `daily-stock-price`. |
| `--exchange` | `HOSE` | Exchange for `index-list`. |
| `--index-code` | `VNINDEX` | Index code for `index-components` and `daily-index`. |
| `--page-index` | `1` | SSI API page number. |
| `--page-size` | `10` | Number of records requested from the SSI endpoint. |
| `--limit` | `3` | Maximum number of sample records printed in the report. |
| `--full-json` | disabled | Prints the complete redacted response envelope. |
| `--timeout` | `30` | HTTP timeout in seconds. |
| `--ascending` | not sent | Sends `ascending=true` to supported OHLC endpoints. |

### `--page-size` versus `--limit`

These options control different things:

- `--page-size` controls how many records the request asks SSI to return.
- `--limit` controls how many detected records are printed under `Sample records`.
- `--full-json` prints the complete redacted response envelope and is not restricted to the sample limit.

Example:

```bash
python scripts/ssi_api_inspector/inspect.py run securities \
  --market HOSE \
  --page-size 100 \
  --limit 5
```

This asks SSI for up to 100 records but prints only the first 5 detected records in the sample section.

### `--ascending`

When `--ascending` is omitted, the CLI does not send the `ascending` parameter.

When it is supplied, the CLI sends:

```text
ascending=true
```

The current CLI does not expose a `--descending` flag and does not explicitly send `ascending=false`.

## Endpoint examples

### Access token

Use this to verify authentication and inspect the redacted token envelope:

```bash
python scripts/ssi_api_inspector/inspect.py run access-token --full-json
```

The actual token and credentials must not appear in output.

### Securities

List securities for a market:

```bash
python scripts/ssi_api_inspector/inspect.py run securities \
  --market HOSE \
  --page-index 1 \
  --page-size 20 \
  --limit 5
```

Use paging to inspect another page:

```bash
python scripts/ssi_api_inspector/inspect.py run securities \
  --market HOSE \
  --page-index 2 \
  --page-size 20 \
  --limit 5
```

### Securities details

Inspect one symbol:

```bash
python scripts/ssi_api_inspector/inspect.py run securities-details \
  --market HOSE \
  --symbol SSI \
  --full-json
```

### Index list

Inspect indexes for an exchange:

```bash
python scripts/ssi_api_inspector/inspect.py run index-list \
  --exchange HOSE \
  --page-size 50 \
  --limit 10
```

### Index components

Inspect the components of an index:

```bash
python scripts/ssi_api_inspector/inspect.py run index-components \
  --index-code VNINDEX \
  --page-size 100 \
  --limit 10
```

### DailyStockPrice

Inspect the canonical daily stock-price endpoint:

```bash
python scripts/ssi_api_inspector/inspect.py run daily-stock-price \
  --symbol SSI \
  --market HOSE \
  --date 10/07/2026 \
  --full-json
```

Use this endpoint to verify daily OHLC, volume, value, foreign-trading fields, and any other fields actually returned by SSI before modifying daily ingest mappings.

### DailyOhlc

Inspect DailyOhlc for comparison with `DailyStockPrice`:

```bash
python scripts/ssi_api_inspector/inspect.py run daily-ohlc \
  --symbol SSI \
  --date 10/07/2026 \
  --ascending \
  --full-json
```

Do not treat this endpoint as the canonical daily source unless the project architecture is changed explicitly.

### IntradayOhlc

Inspect 1-minute intraday OHLCV records:

```bash
python scripts/ssi_api_inspector/inspect.py run intraday-ohlc \
  --symbol SSI \
  --date 10/07/2026 \
  --page-size 1000 \
  --limit 10 \
  --ascending
```

The CLI always sends `resolution=1` for this endpoint.

Do not assume a fixed number such as 226 candles is complete for every trading date. Session structure, trading interruptions, SSI response paging, endpoint behavior, and historical data availability must be checked for the requested date.

### DailyIndex

Inspect daily index data:

```bash
python scripts/ssi_api_inspector/inspect.py run daily-index \
  --index-code VNINDEX \
  --date 10/07/2026 \
  --full-json
```

### Run all data endpoints

```bash
python scripts/ssi_api_inspector/inspect.py run all \
  --symbol SSI \
  --market HOSE \
  --exchange HOSE \
  --index-code VNINDEX \
  --date 10/07/2026 \
  --page-index 1 \
  --page-size 20 \
  --limit 3
```

The same common option values are passed to endpoint builders that use them. Options irrelevant to a specific endpoint are ignored by that endpoint's parameter builder.

## Reading the report

For each endpoint, the CLI prints:

- Endpoint label and CLI name.
- HTTP method and URL.
- Redacted request parameters.
- HTTP status code.
- Request elapsed time.
- Response content type.
- Top-level response keys or top-level response type.
- Common SSI envelope values when present, including `status`, `message`, `responseCode`, and `totalRecord`.
- Detected data-list location.
- Number of detected records.
- Keys from the first record.
- Token-like paths detected in the response.
- Redacted sample records.
- Complete redacted JSON when `--full-json` is enabled.

The inspector searches common list locations such as:

```text
data
dataList
items
```

It also falls back to the first top-level list found in a dictionary response.

## Result statuses

### `PASS`

The inspector found a record list and the list contained at least one record.

`PASS` means the endpoint returned detectable data. It does not prove that every field, date, record, or value is correct.

### `EMPTY`

The inspector did not find any records in the detected list.

Possible causes include:

- Weekend or market holiday.
- No data for the requested historical date.
- Invalid or unsupported symbol.
- Incorrect market, exchange, or index code.
- Requested page is beyond available records.
- SSI returned a different envelope shape.
- Endpoint returned HTTP success with an empty data list.

Do not convert an empty API response into zero-valued market data unless a separate verified business rule explicitly requires that behavior.

### `FAILED`

The endpoint raised an `InspectorError`, for example because of authentication, network, timeout, invalid response, or HTTP failure handling inside the client.

The CLI continues to the next endpoint during `run all`, then prints a summary.

## Exit codes

- Exit code `0`: no endpoint has status `FAILED`.
- Exit code `1`: at least one endpoint has status `FAILED`.

An `EMPTY` endpoint does not currently cause exit code `1`. Review the printed summary instead of relying only on the process exit code when data presence matters.

Example:

```bash
python scripts/ssi_api_inspector/inspect.py run all --date 10/07/2026
echo $?
```

## Troubleshooting

### Missing credentials

Confirm the variables are available in the same shell that runs Python:

```bash
python -c "from src.config import config; print(bool(config.SSI_CONSUMER_ID), bool(config.SSI_CONSUMER_SECRET))"
```

This command prints only booleans. Do not print the real credential values.

### HTTP 401

The client automatically obtains a new token and retries an authenticated request once after HTTP `401`.

If it still fails:

- Verify `SSI_CONSUMER_ID` and `SSI_CONSUMER_SECRET`.
- Verify that the SSI account is active and permitted to call the endpoint.
- Check whether the API host or credentials have changed.
- Do not add unlimited retry loops.

### Empty response

Try a known historical trading date and verify the endpoint-specific identifiers:

```bash
python scripts/ssi_api_inspector/inspect.py run daily-stock-price \
  --symbol SSI \
  --market HOSE \
  --date 10/07/2026 \
  --full-json
```

Check `message`, `responseCode`, `totalRecord`, the detected data-list location, and the complete redacted envelope.

A weekend, holiday, empty SSI response, or unsupported endpoint must remain missing data. Do not create fake rows.

### Unexpected record count

Verify paging before concluding that data is incomplete:

```bash
python scripts/ssi_api_inspector/inspect.py run intraday-ohlc \
  --symbol SSI \
  --date 10/07/2026 \
  --page-index 1 \
  --page-size 1000 \
  --limit 5
```

Compare `totalRecord`, record count in the current response, page size, and page index. Do not hardcode one candle count as the completeness standard for every date.

### Output is too large

Omit `--full-json`, lower `--limit`, or reduce `--page-size`:

```bash
python scripts/ssi_api_inspector/inspect.py run securities \
  --market HOSE \
  --page-size 10 \
  --limit 2
```

### Python import error

Run the script from the project root with the project environment activated:

```bash
pwd
python scripts/ssi_api_inspector/inspect.py list
```

Do not run a copied standalone version of `inspect.py`, because it depends on the package files and `src.config` in this repository.

## Validation and tests

Run the focused offline test file:

```bash
pytest -q tests/test_ssi_api_inspector.py
```

The test suite verifies, among other things:

- The supported endpoint registry.
- Core request parameters.
- POST JSON authentication shape.
- Bearer-token usage and deep redaction.
- Sample-record limits.
- Full JSON redaction.
- Empty-response detection.
- One-time reauthentication after HTTP `401`.
- `run all` summary and exit code.
- Absence of database write imports and calls in the inspector package.

To perform a live SSI smoke check, use an explicit symbol and historical trading date. Live smoke checks require valid SSI credentials and remain read-only:

```bash
python scripts/ssi_api_inspector/inspect.py run daily-stock-price \
  --symbol SSI \
  --market HOSE \
  --date 10/07/2026 \
  --limit 1
```

## Current limitations

- The date option currently represents one explicit date and is used as both `FromDate` and `ToDate`.
- Intraday resolution is fixed at 1 minute.
- The CLI does not expose explicit `--from-date` and `--to-date` options.
- The CLI does not expose `--descending` or explicit `ascending=false`.
- `run all` uses one shared set of CLI arguments for endpoint-specific builders.
- The inspector reports the API response but does not determine whether the returned rows are complete or semantically correct for ingestion.
- The inspector does not write raw or clean tables.
- The inspector does not trigger feature, signal, or backtest pipelines.

Any future CLI change must preserve read-only behavior by default and should update this README, parser tests, endpoint tests, and troubleshooting instructions in the same task.
