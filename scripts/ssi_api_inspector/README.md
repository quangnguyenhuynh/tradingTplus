# SSI REST API Inspector

A read-only command-line tool for inspecting SSI REST responses without using the production ingest pipeline or database. It prints the actual source, endpoint, sanitized request, response envelope, paging metadata, raw and mapped clean samples, and optionally the complete raw response plus all mapped clean rows with sensitive values redacted. It does **not** prove completeness or semantic correctness, and does not run features, signals, or backtests.

> REST v3 is the inspector default. REST v2 is legacy and runs only with `--data-source ssi_v2`. There is no automatic fallback or automatic v2/v3 comparison. Production ingestion remains unchanged on its configured source.

## Install and credentials

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requests` and `python-dotenv` are supplied by `requirements.txt`. Configure only the selected source:

```env
# v3
SSI_API_KEY=replace_me
SSI_API_SECRET=replace_me

# legacy v2
SSI_CONSUMER_ID=replace_me
SSI_CONSUMER_SECRET=replace_me
```

V3 market-data inspection does not require v2 credentials, client ID, private key, or OTP. V2 does not require v3 credentials. Tokens remain in memory and are never cached. `list` and help need neither credentials nor network. Never print or commit `.env`.

## CLI

```bash
python scripts/ssi_api_inspector/inspect.py --help
python scripts/ssi_api_inspector/inspect.py list
python scripts/ssi_api_inspector/inspect.py list --data-source ssi_v2
python scripts/ssi_api_inspector/inspect.py run <endpoint> [options]
python scripts/ssi_api_inspector/inspect.py run all [options]
```

Common options are `--data-source`, `--symbol`, `--board`, compatibility aliases `--market`/`--exchange`, `--index-code`, `--date`, `--from-date`, `--to-date`, `--page-index`, `--page-size`, `--limit`, `--full-json`, `--show-mapping`, `--timeout`, and `--ascending`.

Dates accept `DD/MM/YYYY` and `YYYY-MM-DD`. Use either `--date` or the complete `--from-date`/`--to-date` pair; ranges must be ordered. V3 summary/daily/master values are sent as `from`/`to` in `YYYY/MM/DD`; v3 intraday uses `from` at `00:00:00` and `to` at `23:59:59` without host-timezone conversion. `index-summary`/`daily-index` accepts one `--date` only. Intraday OHLC is fixed to `1m`.

### CLI date input to REST query

| Source/endpoint | Query sent | Timeframe |
|---|---|---|
| V3 `securities-summary` / `daily-stock-price` | `from`, `to` (`YYYY/MM/DD`) | omitted |
| V3 `daily-ohlc` | `from`, `to` (`YYYY/MM/DD 00:00:00`) | `timeFrame=1d` |
| V3 `intraday-ohlc` | `from`, `to` (`YYYY/MM/DD HH:MM:SS`) | `timeFrame=1m` |
| V3 `master-data` | `from`, `to` (`YYYY/MM/DD`) | omitted |
| V3 `index-summary` / `daily-index` | `tradingDate` (`YYYY/MM/DD`) | omitted |
| V2 dated endpoints | `FromDate`, `ToDate` (`DD/MM/YYYY`) | legacy endpoint contract; intraday retains `resolution=1` |

`--page-size` controls the page requested from SSI. `--limit` controls both raw and clean samples. `--full-json` prints the complete raw response and all corresponding clean rows in separate JSON sections. Raw field names, types and unknown fields are preserved, except secret redaction. One command fetches exactly one requested page; mapping uses that response without another API call.

## Endpoint registry

### V3 (default)

| CLI name | HTTP/API | Required contract | Compatibility aliases |
|---|---|---|---|
| `access-token` | POST `/api/v3/auth/token` | JSON `apiKey`, `apiSecret` | — |
| `securities-by-board` | GET `/api/v3/data/securitiesByBoard` | exactly one of symbol/board/index | `securities` (board), `securities-details` (symbol), `index-components` (index) |
| `securities-summary` | GET `/api/v3/data/securitiesSummary` | exactly one symbol/index, dates, paging | `daily-stock-price` (symbol only) |
| `index-list` | GET `/api/v3/data/indexList` | optional board | — |
| `index-summary` | GET `/api/v3/data/indexSummary` | exactly one board/index and one date | `daily-index` (index only) |
| `daily-ohlc` | GET `/api/v3/data/ohlc` | symbol, dates, `timeFrame=1d`, paging | — |
| `intraday-ohlc` | GET `/api/v3/data/ohlc` | symbol, datetimes, `timeFrame=1m`, paging | — |
| `master-data` | GET `/api/v3/data/masterdata` | dates and paging; no symbol | — |

### Legacy v2

V2 preserves: `access-token`, `securities`, `securities-details`, `index-components`, `index-list`, `daily-ohlc`, `intraday-ohlc`, `daily-index`, and `daily-stock-price`. Always add `--data-source ssi_v2`. A name unsupported by the chosen source fails explicitly.

`run all` calls each unique **data** endpoint for only the selected source, authenticates as needed, does not separately report `access-token`, uses endpoint-specific parameters, continues after failures, then prints a summary.

## Examples

```bash
python scripts/ssi_api_inspector/inspect.py run access-token --full-json
python scripts/ssi_api_inspector/inspect.py run securities-by-board --board HOSE --full-json
python scripts/ssi_api_inspector/inspect.py run securities --market HOSE
python scripts/ssi_api_inspector/inspect.py run securities-details --symbol SSI
python scripts/ssi_api_inspector/inspect.py run index-components --index-code VNINDEX
python scripts/ssi_api_inspector/inspect.py run index-list --board HOSE
python scripts/ssi_api_inspector/inspect.py run securities-summary --symbol SSI --from-date 01/09/2026 --to-date 08/09/2026 --page-index 1 --page-size 20 --full-json
python scripts/ssi_api_inspector/inspect.py run securities-summary --symbol SSI --date 08/09/2026 --full-json
# Compatibility alias for the same v3 native endpoint:
python scripts/ssi_api_inspector/inspect.py run daily-stock-price --symbol SSI --date 08/09/2026 --full-json
python scripts/ssi_api_inspector/inspect.py run daily-index --index-code VNINDEX --date 08/09/2026 --full-json
python scripts/ssi_api_inspector/inspect.py run daily-ohlc --symbol SSI --date 2026-09-08
python scripts/ssi_api_inspector/inspect.py run intraday-ohlc --symbol SSI --date 08/09/2026 --page-index 1 --page-size 100 --full-json
python scripts/ssi_api_inspector/inspect.py run master-data --date 08/09/2026 --full-json
python scripts/ssi_api_inspector/inspect.py run all --symbol SSI --board HOSE --index-code VNINDEX --date 08/09/2026 --limit 3
```

Manual same-symbol/date comparison (outputs are not automatically compared and the tool makes no field-equivalence claim):

```bash
python scripts/ssi_api_inspector/inspect.py run daily-stock-price --symbol SSI --date 08/09/2026 --full-json > /tmp/ssi-v3.txt
python scripts/ssi_api_inspector/inspect.py run daily-stock-price --data-source ssi_v2 --symbol SSI --date 08/09/2026 --full-json > /tmp/ssi-v2.txt
```

## Output, status, and security

Reports include selected source; native endpoint and alias; method; actual sanitized URL and parameters; HTTP status and elapsed time; Content-Type; related rate-limit headers; top-level type/keys; data-list location (`$`, `data`, `dataList`, `items`, or supported nested envelope); current-page record count; provider paging values (`pageIndex`, `pageSize`, `pagesCount`, `itemsCount`, `totalRecord`); first-record keys; sample rows; and optional full body.

- **PASS**: valid endpoint shape with data and no mapping errors where a mapping is registered; auth passes when a token exists.
- **EMPTY**: valid data list is present but empty. It does not prove a non-trading day.
- **FAILED**: transport/auth/HTTP/API error, invalid shape, empty HTTP body, non-JSON response, or mapping failure. API and mapping statuses are printed separately.
- Exit `0` means no `FAILED`; exit `1` means at least one `FAILED`; syntax errors use argparse exit `2`.

JSON errors, HTTP 4xx/5xx bodies, empty bodies, and non-JSON text are retained for reporting rather than replaced with `[]`. The raw section stays independent of mapping, including when mapping fails. Sensitive key values—including nested API keys/secrets, consumer credentials, tokens, refresh tokens, and Authorization—are redacted. Configured secret/token values echoed in text or exceptions are scrubbed. Redirects are refused, retry and 401 recovery are bounded, and tokens are never written to disk.

## Raw to clean mapping

```bash
python scripts/ssi_api_inspector/inspect.py run daily-stock-price --symbol SSI --date 08/09/2026 --full-json --show-mapping
```

The default API is the newest supported inspector source, currently `ssi_v3`. `--data-source ssi_v2` selects the legacy source for manual comparison. `data-preview` is no longer a command in `main.py`.

| Existing clean dataset | V2 endpoint | V3 endpoint |
|---|---|---|
| `stock_daily` | `daily-stock-price` | `securities-summary` (alias `daily-stock-price`) |
| `stock_intraday` (1m) | `intraday-ohlc` | `intraday-ohlc` |
| `index_daily` | `daily-index` | `index-summary` (alias `daily-index`) |

`src/data_contracts/mappings/ssi_v2.json` and `ssi_v3.json` supply the field rules and the `inspector` endpoint/prefix metadata. `src/data_contracts/definitions.json` defines the unchanged clean fields. The inspector passes each response row through the shared mapping engine; mapping never changes raw data. `--show-mapping` prints the rules. Mapping diagnostics show missing fields, unused raw fields and errors. Unverified fields stay null with their reason. A rejected record is shown as `null` in the clean list, at the same position as its raw record, with diagnostics. Empty responses produce an empty clean list.

For intraday, the existing `round(close * volume)` helper supplies estimated value; no extra daily request or feature computation runs. Per-record source dates are retained for ranges; a missing date is not replaced by the range start. DailyOHLC remains a raw cross-check and is not mapped into canonical stock daily data. Endpoints without a registered mapping explicitly report raw-only output.

The flow ends after printing. No database client, write option, ingest, feature, signal or backtest is invoked. No migration or backfill is needed. A new provider can keep the same clean contract by adding its source dictionary and endpoint metadata; its authentication/request adapter still needs to exist. Production ingestion is a later, separately requested step.

## Troubleshooting

- **401:** verify credentials for the selected source. The client performs at most one authentication recovery cycle.
- **403:** verify SSI entitlement and source; do not add OTP/private-key requirements unless SSI's REST contract requires them.
- **429:** honor the displayed rate-limit metadata; bounded retry respects `Retry-After` within a capped wait.
- **Timeout/5xx:** increase `--timeout` within 1–120 seconds or retry later; retries are bounded.
- **EMPTY:** verify identifier, trading date, page, and provider envelope. Do not fabricate rows or conclude it was a holiday.
- **Non-JSON/malformed JSON:** use `--full-json` to inspect sanitized text; status remains `FAILED`.

Official reference: [SSI API Reference](https://developers.ssi.com.vn/docs/api-reference). Supplemental examples: [official SSI FastConnect v3 tutorials](https://github.com/SSI-Securities-Inc/ssi-fastconnect-v3-tutorials). Contract references: SSI API Reference and the official FastConnect v3 tutorial/request models. **Live verification status: UNVERIFIED / NOT_RUN unless the final implementation report states otherwise.** Offline fixtures reproduce body `code=400` / `msg=invalid timeframe`, but that fixture is not an observed SSI response and does not prove the reported live issue is resolved.

## Tests and read-only live smoke

```bash
pytest -q tests/inspectors/test_ssi_api_inspector.py tests/inspectors/test_ssi_api_mapping.py tests/data_contracts
python -m compileall scripts/ssi_api_inspector
python scripts/ssi_api_inspector/inspect.py --help
python scripts/ssi_api_inspector/inspect.py list
python scripts/ssi_api_inspector/inspect.py list --data-source ssi_v2
```

Only run a live request when the appropriate credentials already exist. Use an explicit symbol/date; the inspector never reads or writes Supabase.
