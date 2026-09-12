# SSI REST API Inspector

This standalone CLI reads SSI APIs, preserves the fetched RAW response, maps that same response through the shared data-contract engine, and prints CLEAN candidates plus diagnostics. It never initializes a database client, writes Supabase, or runs ingest, features, signals, or backtests.

## Canonical dataset CLI

```bash
python scripts/ssi_api_inspector/inspect.py run <dataset> [options]

python scripts/ssi_api_inspector/inspect.py run stock-daily --symbol SSI --date 2026-09-08
python scripts/ssi_api_inspector/inspect.py run stock-intraday --symbol SSI --date 2026-09-08
python scripts/ssi_api_inspector/inspect.py run index-daily --index-code VNINDEX --date 2026-09-08
```

The canonical names do not change when the provider changes:

```bash
python scripts/ssi_api_inspector/inspect.py run stock-daily --symbol SSI --date 2026-09-08 --data-source ssi_v2
python scripts/ssi_api_inspector/inspect.py run stock-daily --symbol SSI --from-date 2026-09-01 --to-date 2026-09-08
python scripts/ssi_api_inspector/inspect.py run stock-daily --symbol SSI --date 2026-09-08 --full-json --show-mapping
```

`stock-daily` maps to `stock_daily`; `stock-intraday` maps to `stock_intraday` with fixed `timeframe=1m`; `index-daily` maps to `index_daily`. Stock datasets require exactly `--symbol`; index daily requires exactly `--index-code`. Dates prefer `YYYY-MM-DD` and continue to accept `DD/MM/YYYY`. Supply either `--date` or both ordered `--from-date` and `--to-date`; no date is inferred.

## Source selection and routing

Without `--data-source`, the inspector uses capability registry order to select the newest registered source supporting that dataset. This currently selects **ssi_v3 (preview)** for all three datasets. Preview means inspector-only and does not mean complete, semantically verified, or production-ready. Production independently selects the newest **ready** source and remains on ssi_v2.

| Canonical dataset | CLEAN contract | ssi_v2 (ready) | ssi_v3 (preview) |
|---|---|---|---|
| `stock-daily` | `stock_daily` | `daily-stock-price` | `securities-summary` |
| `stock-intraday` | `stock_intraday` (1m) | `intraday-ohlc` | `intraday-ohlc` |
| `index-daily` | `index_daily` | `daily-index` | `index-summary` |

Routing comes from each source mapping's `inspector.endpoint` metadata and is checked against the native endpoint registry before network access. There is no fallback after an explicit choice or after credential, HTTP, empty-response, or mapping failures. A future source requires a registered capability, authentication/request adapter and mapping metadata/rules; the canonical CLI needs no provider-specific name.

Credentials are source-specific: v3 uses `SSI_API_KEY`/`SSI_API_SECRET`; v2 uses `SSI_CONSUMER_ID`/`SSI_CONSUMER_SECRET`. Tokens remain in memory. Help and `list` need neither credentials nor network:

```bash
python scripts/ssi_api_inspector/inspect.py --help
python scripts/ssi_api_inspector/inspect.py run --help
python scripts/ssi_api_inspector/inspect.py list
python scripts/ssi_api_inspector/inspect.py list --data-source ssi_v2
```

`list` shows canonical dataset capabilities, readiness/preview status and routed endpoint, followed by the selected source's endpoint compatibility view.

## Dates, request plans and paging

Provider builders retain their tested contracts. V2 uses `FromDate`/`ToDate` in `DD/MM/YYYY` and intraday `resolution=1`. V3 securities summary uses date-only `from`/`to`; v3 intraday OHLC uses day-boundary timestamps plus `timeFrame=1m`. The CLI does not append time to endpoints that do not require it.

Canonical datasets accept a day or range. Range-capable endpoints receive one range request. Because v3 `index-summary` accepts one date, an index range becomes one request per calendar date, each with its own request/date context; an empty day remains `EMPTY`, not a fabricated holiday row. A canonical invocation is rejected before network access if its plan exceeds 100 data requests. If one request fails, remaining planned requests run, but final exit is nonzero.

`--page-index` and `--page-size` request one page only where supported. Explicit paging options are rejected for a non-paged endpoint. There is no fetch-all mode. `--limit` only limits RAW/CLEAN samples **per response**. `--full-json` prints the complete response actually fetched and all corresponding CLEAN candidates; it does not fetch more pages. Reports state whether paging applies and the current/total planned request.

## RAW, CLEAN and status

The flow is:

```text
canonical request -> capability/source -> native endpoint request -> RAW
                  -> source+dataset mapping -> CLEAN + diagnostics -> print
```

The mapper receives the response already fetched; it never calls SSI again. RAW field names, types and unknown fields remain intact except display redaction. CLEAN uses `src/data_contracts/definitions.json` and source mappings, not an inspector-specific contract. Missing/unverified fields remain `null` with diagnostics; malformed, identity/date-mismatched, or conversion-failing records remain traceable by raw record number. Errors outside the displayed sample still fail the run. Intraday estimated value keeps the existing `round(close * volume)` helper and does not reinterpret volume.

Output includes dataset, requested source (`auto` or explicit), resolved source/status, native endpoint, redacted params/URL, range/request context, HTTP/API status, record count, paging metadata, RAW, CLEAN, mapping version, missing/unsupported/unverified fields and conversion errors.

- **PASS:** response shape contains records and all mapped records pass. It does not prove completeness or production readiness.
- **EMPTY:** a valid data list is empty. It does not prove the date is a holiday.
- **FAILED:** validation, auth, transport, HTTP/API/envelope, response-shape, or mapping failure.
- Exit `0`: no request failed; exit `1`: at least one request failed; argparse validation: exit `2`.

Secrets in keys, URLs, JSON, text and exceptions are redacted/scrubbed. Redirects are refused; retries and the single 401 recovery cycle are bounded.

## Endpoint compatibility mode

Existing endpoint commands continue to work for direct provider inspection:

```bash
python scripts/ssi_api_inspector/inspect.py run securities-summary --symbol SSI --date 2026-09-08
python scripts/ssi_api_inspector/inspect.py run daily-stock-price --data-source ssi_v2 --symbol SSI --date 2026-09-08
python scripts/ssi_api_inspector/inspect.py run daily-ohlc --symbol SSI --date 2026-09-08
python scripts/ssi_api_inspector/inspect.py run all --symbol SSI --board HOSE --index-code VNINDEX --date 2026-09-08
```

Compatibility aliases do not duplicate native endpoints in `run all`; `run all` retains its existing endpoint set and behavior. `daily-ohlc` remains a RAW cross-check and is not canonical `stock_daily`. Catalog/auth endpoints and their endpoint-specific options remain available.

## Verification limits

Offline tests/fixtures validate orchestration, parameter shapes, RAW preservation and mapping behavior; they do not prove live SSI response semantics, entitlement, availability or completeness. Live status is **NOT_RUN / UNVERIFIED** unless a specific implementation report says otherwise. A read-only live check requires already-configured credentials and explicit SSI/VNINDEX dates. No migration, DB data change or backfill is involved.
