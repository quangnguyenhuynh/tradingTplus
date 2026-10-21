# SSI v3 REST inspector runbook

[Tiếng Việt](README.vi.md) · [Production CLI](../../../docs/CLI_USAGE.md)

## Purpose and dependencies

Run every command from the repository root. This tool is READ-ONLY with respect to Supabase: it never constructs a database client or persists market data. `list` and help are local; `run` can authenticate and make live SSI requests. Install requirements in the Python 3.11 virtual environment and configure `SSI_API_KEY`, `SSI_API_SECRET` locally in `.env`; no Supabase credentials are required. Do not print tokens or commit response files containing sensitive account data.

Inspection does not enable production ingestion. Stock Daily/Index Daily are ready for ingest; stock-intraday, symbol-list and index-list are preview capabilities. Master-data inspection is a native endpoint, not an implemented master synchronization pipeline. Catalog responses are current query snapshots with unverified completeness, not dated catalog history.

## Commands and datasets

The examples below cover help/list, stock/index preview, historical clean-mapping inspection for 1m, daily OHLC cross-check, catalogs, master data, pagination and date ranges. All `run` examples are READ-ONLY — SSI API request. `--full-json` prints the entire returned response, not all pages.

```bash
python scripts/inspectors/ssi_rest/inspect.py --help
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run --help
python scripts/inspectors/ssi_rest/inspect.py run stock-daily --symbol SSI --date 2026-10-19 --data-source ssi_v3 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run index-daily --index-code VNINDEX --date 2026-10-19 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --limit 5 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run daily-ohlc --symbol SSI --date 2026-10-19 --ascending
python scripts/inspectors/ssi_rest/inspect.py run symbol-list --board HOSE --limit 5
python scripts/inspectors/ssi_rest/inspect.py run index-list --limit 5
python scripts/inspectors/ssi_rest/inspect.py run master-data --from-date 2026-10-01 --to-date 2026-10-19 --limit 5
python scripts/inspectors/ssi_rest/inspect.py run stock-daily --symbol SSI --from-date 2026-10-01 --to-date 2026-10-19 --page-index 2 --page-size 20 --full-json
python scripts/inspectors/ssi_rest/inspect.py run index-daily --index-code VNINDEX --from-date 2026-10-01 --to-date 2026-10-19 --limit 3
python scripts/inspectors/ssi_rest/inspect.py run securities-by-board --symbol SSI
python scripts/inspectors/ssi_rest/inspect.py run securities-by-board --index-code VN30
python scripts/inspectors/ssi_rest/inspect.py run securities-summary --symbol SSI --date 2026-10-19
python scripts/inspectors/ssi_rest/inspect.py run index-summary --index-code VNINDEX --date 2026-10-19
```
| CLI dataset | Native endpoint | Selector | Dates / Ngày | Paging |
| --- | --- | --- | --- | --- |
| stock-daily | securities-summary | --symbol SSI | --date / --from-date + --to-date | Yes / Có |
| stock-intraday | intraday-ohlc | --symbol SSI | --date / --from-date + --to-date | Yes / Có |
| index-daily | index-summary | --index-code VNINDEX | --date / --from-date + --to-date | No / Không |
| symbol-list | securities-by-board | --board HOSE | None / Không | No / Không |
| index-list | index-list | optional / tùy chọn --board | None / Không | No / Không |

## Native endpoints and compatibility aliases

The only base URL is `https://api.ssi.com.vn/api/v3`. Native endpoints: `access-token` (POST `/auth/token`), `securities-by-board` (`/data/securitiesByBoard`), `securities-summary` (`/data/securitiesSummary`), `index-list` (`/data/indexList`), `index-summary` (`/data/indexSummary`), `daily-ohlc` and `intraday-ohlc` (both `/data/ohlc`, timeFrame 1d/1m), and `master-data` (`/data/masterdata`).

`securities-by-board` selects exactly one symbol/board/index-code. `securities-summary` selects symbol or index-code with a date/range. Native `index-summary` selects board or index-code with one date only. `master-data` accepts a date/range; raw inspection remains possible without clean mapping.

Lookup aliases are not separate native v3 endpoints:

| Alias | Native | Selector |
| --- | --- | --- |
| securities | securities-by-board | --board or --market |
| securities-details | securities-by-board | --symbol |
| index-components | securities-by-board | --index-code |
| daily-stock-price | securities-summary | --symbol + date |
| daily-index | index-summary | --index-code + date |

`run all` invokes seven native data endpoints (not a separate auth invocation, no alias duplication); it can make many requests, with endpoint-specific selectors. Prefer an individual dataset to control scope.

## Dates, pagination and limits

Dates accept DD/MM/YYYY or YYYY-MM-DD. Select either `--date` or both `--from-date`/`--to-date`, never both forms. Canonical index-daily ranges create one request per calendar day, maximum 100 requests; this does not prove each day is a session. Catalogs reject dates; symbol-list requires board. Canonical catalogs accept --market/--exchange as board aliases, but conflicting values fail. Canonical stock/index requests reject board/market/exchange and ascending; native OHLC supports `--ascending`.

Defaults: page-index 1, page-size 10, display limit 3, timeout 30 seconds. Only the requested page is fetched; `--limit` controls display, not page size or request count. Explicit paging is rejected for canonical index-summary/securities-by-board/index-list plans without paging. Request a specific page on endpoints that support it; one page is not full history. Timeout must be 1–120, limit nonnegative, page-index/page-size positive. Code caveat: zero is replaced by defaults via `or` before validation, so avoid zero.

## Raw, clean, mapping and errors

Reports show resolved dataset/source, redacted endpoint URL/params, HTTP status, elapsed time, response type/list location, received/displayed counts, paging metadata, raw samples and clean samples when mapping exists. `--show-mapping` adds field rules and preview-only fields; `--full-json` adds complete raw, clean and diagnostic output for the returned response. Missing required/optional fields, unused source fields and errors distinguish API success from mapping success. Unverified fields remain null; endpoints without mappings are raw-only.

The actual dictionary is `src/contracts/mappings/ssi_v3.json`. An old printed diagnostic string still says `src/data_contracts/mappings/...`; that is a code issue, not the current path.

Exit 0 means no FAILED result (PASS or EMPTY); exit 1 indicates request/HTTP/auth/mapping failure; exit 2 indicates parser or canonical-plan validation failure. Native option errors may be caught as FAILED/exit 1. EMPTY does not certify coverage; PASS does not certify persistence. For 401/403 inspect local v3 key/secret and account entitlement; narrow a timeout scope; preserve raw/mapping diagnostics on mapping failure. Do not retry with a retired source or change mapping/source behavior in a documentation task.

Examples were checked with offline parser/planning and mock tests, not live SSI/Supabase calls.

## All run arguments

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `endpoint` | yes | `—` | 1 |
| `--data-source` | no | `"ssi_v3"` | ssi_v3 |
| `--symbol` | no | `—` | 1 |
| `--date` | no | `—` | 1 |
| `--from-date` | no | `—` | 1 |
| `--to-date` | no | `—` | 1 |
| `--board` | no | `—` | 1 |
| `--market` | no | `—` | 1 |
| `--exchange` | no | `—` | 1 |
| `--index-code` | no | `—` | 1 |
| `--page-index` | no | `—` | 1 |
| `--page-size` | no | `—` | 1 |
| `--limit` | no | `3` | 1 |
| `--full-json` | no | `false` | flag |
| `--show-mapping` | no | `false` | flag |
| `--timeout` | no | `30` | 1 |
| `--ascending` | no | `—` | flag |
