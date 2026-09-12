#!/usr/bin/env python
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) in sys.path:
    sys.path.remove(str(SCRIPT_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ssi_api_inspector.client import (InspectorClient, InspectorError,
                                               find_token_paths, redact, scrub_text)
from scripts.ssi_api_inspector.endpoints import (DATA_SOURCES, DEFAULT_DATA_SOURCE, RUN_ALL_ORDER,
                                                  ParameterError, registry)
from scripts.ssi_api_inspector.mapping import endpoint_mapping, map_rows
from scripts.ssi_api_inspector.datasets import (CLI_DATASETS, DatasetRequest,
                                                 build_dataset_plan, canonical_capabilities)
from src.data_contracts.registry import MappingConfigurationError

LIST_KEYS = ("data", "dataList", "items")
PAGING_KEYS = ("pageIndex", "pageSize", "pagesCount", "itemsCount", "totalRecord")


def _data_location(body: Any) -> tuple[str | None, list[Any] | None]:
    if isinstance(body, list):
        return "$", body
    if isinstance(body, dict):
        for key in LIST_KEYS:
            if isinstance(body.get(key), list):
                return key, body[key]
        for outer in ("data", "result", "response"):
            nested = body.get(outer)
            if isinstance(nested, dict):
                for key in LIST_KEYS:
                    if isinstance(nested.get(key), list):
                        return f"{outer}.{key}", nested[key]
    return None, None


def _lookup(body: Any, key: str) -> Any:
    if not isinstance(body, dict):
        return None
    for actual, value in body.items():
        if str(actual).lower() == key.lower():
            return value
    for value in body.values():
        found = _lookup(value, key)
        if found is not None:
            return found
    return None


def _api_error(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    # Error markers are envelope fields. Do not recursively interpret fields in
    # otherwise valid data records as provider status codes.
    candidates = [body]
    candidates.extend(body[key] for key in ("result", "response") if isinstance(body.get(key), dict))
    for candidate in candidates:
        envelope = {str(key).lower(): value for key, value in candidate.items()}
        success = envelope.get("success")
        if success is False:
            return str(envelope.get("message") or "success=false")
        error = envelope.get("error")
        if error not in (None, "", False, [], {}):
            return str(error)
        status = envelope.get("status")
        if isinstance(status, str) and status.lower() in {"error", "failed", "failure"}:
            return str(envelope.get("message") or status)
        code = envelope.get("responsecode")
        if code is not None and str(code).strip().lower() not in {"0", "00", "200", "success", "ok"}:
            return f"responseCode={code}: {envelope.get('message') or 'API request failed'}"
        # REST v3 uses a top-level code/msg envelope. Successful codes observed
        # in the documented contract are 0/00/200; record codes are ignored.
        code = envelope.get("code")
        if code is not None and str(code).strip().lower() not in {"0", "00", "200", "success", "ok"}:
            return f"code={code}: {envelope.get('msg') or envelope.get('message') or 'API request failed'}"
    return None


def _safe_url(url: str) -> str:
    parts = urlsplit(url)
    query = [(key, "[REDACTED]" if any(p in key.replace("_", "").lower() for p in ("token", "secret", "apikey", "consumerid")) else value)
             for key, value in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _print_json(value: Any) -> None:
    print(json.dumps(redact(value), indent=2, ensure_ascii=False, default=str))


def print_report(source: str, endpoint: Any, params: dict[str, Any], response: Any,
                 *, limit: int, full_json: bool, client: InspectorClient | None = None,
                 show_mapping: bool = False, dataset: str | None = None,
                 requested_source: str | None = None, source_status: str | None = None,
                 request_number: int = 1, request_count: int = 1,
                 request_label: str | None = None, paging_supported: bool | None = None) -> str:
    location, rows = _data_location(response.body)
    error = _api_error(response.body)
    if response.status_code >= 400 or response.json_state in {"empty", "non-json"} or error:
        status = "FAILED"
    elif endpoint.response_kind == "auth":
        from scripts.ssi_api_inspector.client import extract_access_token
        status = "PASS" if extract_access_token(response.body) else "FAILED"
    elif rows is None:
        status = "FAILED"
    else:
        status = "PASS" if rows else "EMPTY"

    print("\n" + "=" * 88)
    if dataset:
        print(f"Dataset requested: {dataset}")
        print(f"Data source requested: {requested_source or 'auto'}")
        print(f"Data source resolved: {source} ({source_status})")
        print(f"Request: {request_number}/{request_count} ({request_label})")
    print(f"Data source: {source}")
    print(f"Endpoint: {endpoint.native_name}" + (f" (CLI alias: {endpoint.name})" if endpoint.alias_for else ""))
    print(f"Method: {endpoint.method}")
    print(f"URL: {_safe_url(response.actual_url or endpoint.url)}")
    print(f"Request params: {json.dumps(redact(params), ensure_ascii=False, default=str)}")
    print(f"HTTP status: {response.status_code}")
    print(f"Elapsed seconds: {response.elapsed_sec:.3f}")
    print(f"Content-Type: {response.content_type or '(missing)'}")
    print(f"Rate-limit headers: {response.rate_limit_headers or {}}")
    if response.json_state == "json":
        print(f"Top-level response type: {type(response.body).__name__}")
        if isinstance(response.body, dict):
            print(f"Top-level response keys: {sorted(str(k) for k in response.body)}")
    else:
        print(f"Response body type: {response.json_state}")
    print(f"Data list location: {location or 'not found'}")
    print(f"Record count in current response: {len(rows) if rows is not None else 'n/a'}")
    paging = {key: _lookup(response.body, key) for key in PAGING_KEYS if _lookup(response.body, key) is not None}
    if paging_supported is not None:
        print(f"Paging applied: {'yes (one requested page)' if paging_supported else 'no (endpoint does not page)'}")
    print(f"Paging metadata (provider-reported): {json.dumps(redact(paging), ensure_ascii=False, default=str)}")
    first_keys = sorted(str(key) for key in rows[0]) if rows and isinstance(rows[0], dict) else []
    print(f"First record keys: {first_keys}")
    token_paths = find_token_paths(response.body)
    if token_paths:
        print(f"Sensitive fields detected and redacted: {token_paths}")
    print(f"API status: {status}")
    if error:
        print(f"API error: {scrub_text(error, [client.token] if client and client.token else [])}")
    elif response.status_code >= 400:
        safe_error_body = (redact(response.body) if response.json_state == "json"
                           else scrub_text(response.text, [client.token] if client and client.token else []))
        print(f"HTTP error body: {safe_error_body}")
    print(f"Raw sample records (limit={limit}):")
    _print_json((rows or [])[:max(0, limit)])
    if full_json:
        if response.json_state == "json":
            print("Full raw JSON (redacted only):")
            _print_json(response.body)
        else:
            print("Full raw response text (redacted):")
            print(scrub_text(response.text, [client.token] if client and client.token else []))
    if endpoint.response_kind != "auth":
        if status == "FAILED":
            print("Clean mapping: skipped because the API response failed")
        else:
            selected = endpoint_mapping(source, endpoint.native_name)
            if selected is None:
                print("Clean mapping: unavailable for this endpoint; raw inspection only")
            else:
                dataset, mapping = selected
                clean, reports = map_rows(source, dataset, mapping, rows, params)
                failed = any(report["errors"] for report in reports)
                print(f"Clean dataset: {dataset}")
                print(f"Mapping dictionary: src/data_contracts/mappings/{source}.json ({mapping['mapping_version']})")
                print(f"Mapping status: {'FAILED' if failed else 'EMPTY' if not rows else 'PASS'}")
                print("Full clean JSON:" if full_json else f"Clean sample records (limit={limit}):")
                _print_json(clean if full_json else clean[:limit])
                print("Mapping diagnostics (record numbers refer to the raw page):")
                displayed = reports if full_json else reports[:limit] + [report for report in reports[limit:] if report["errors"]]
                keys = ("record", "missing_required", "missing_optional", "unused_source_fields", "errors")
                _print_json([{key: report[key] for key in keys if report.get(key)} for report in displayed])
                unsupported = {field: rule["reason"] for field, rule in mapping["fields"].items() if rule.get("unsupported")}
                if unsupported:
                    print("Unverified clean fields (kept null):")
                    _print_json(unsupported)
                if show_mapping:
                    print("Mapping rules (raw aliases/context -> existing clean fields):")
                    _print_json(mapping["fields"])
                if failed:
                    status = "FAILED"
    return status


def run_one(client: InspectorClient, source: str, name: str, args: argparse.Namespace) -> str:
    endpoint = registry(source)[name]
    if endpoint.response_kind == "auth":
        client.require_credentials()
    endpoint_args = args
    if source == "ssi_v3" and args.endpoint == "all":
        endpoint_args = copy.copy(args)
        if name == "securities-by-board":
            endpoint_args.symbol = endpoint_args.index_code = None
            endpoint_args.board = endpoint_args.board or endpoint_args.market
        elif name == "securities-summary":
            endpoint_args.index_code = None
        elif name == "index-summary":
            endpoint_args.board = None
    else:
        _validate_endpoint_options(source, endpoint, endpoint_args)
    params = endpoint.build_params(endpoint_args)
    post_json = endpoint.post_json(endpoint_args) if endpoint.post_json else None
    response = client.request_endpoint(endpoint, params, post_json)
    return print_report(source, endpoint, params, response, limit=args.limit,
                        full_json=args.full_json, client=client,
                        show_mapping=getattr(args, "show_mapping", False))


def _add_source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-source", choices=DATA_SOURCES, default=DEFAULT_DATA_SOURCE,
                        help="SSI REST source (default: newest registered inspector-capable source)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only SSI REST API inspector (v3 by default).")
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="List endpoints for one source; no credentials/network required")
    _add_source(listing)
    run = sub.add_parser("run", help="Run one endpoint or all data endpoints")
    run.add_argument("endpoint", help="Canonical dataset, endpoint name, compatibility alias, or 'all'")
    _add_source(run)
    run.add_argument("--symbol")
    run.add_argument("--date", help="One date in DD/MM/YYYY or YYYY-MM-DD")
    run.add_argument("--from-date", help="Range start in DD/MM/YYYY or YYYY-MM-DD")
    run.add_argument("--to-date", help="Range end in DD/MM/YYYY or YYYY-MM-DD")
    run.add_argument("--board")
    run.add_argument("--market", help="Compatibility alias for board where supported")
    run.add_argument("--exchange", help="Compatibility alias for board where supported")
    run.add_argument("--index-code")
    run.add_argument("--page-index", type=int, default=None)
    run.add_argument("--page-size", type=int, default=None)
    run.add_argument("--limit", type=int, default=3)
    run.add_argument("--full-json", action="store_true")
    run.add_argument("--show-mapping", action="store_true", help="Print the source dictionary rules used for clean output")
    run.add_argument("--timeout", type=int, default=30)
    run.add_argument("--ascending", action="store_true", default=None)
    return parser


def _validate_numeric(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.page_index < 1 or args.page_size < 1 or args.limit < 0 or not 1 <= args.timeout <= 120:
        parser.error("page-index/page-size must be positive, limit non-negative, and timeout 1..120")


def run_dataset(args: argparse.Namespace) -> dict[str, str]:
    dataset = CLI_DATASETS[args.endpoint]
    request = DatasetRequest(
        dataset=dataset, symbol=args.symbol, index_code=args.index_code,
        date=args.date, from_date=args.from_date, to_date=args.to_date,
        page_index=args.page_index, page_size=args.page_size, ascending=args.ascending,
        board=args.board, market=args.market, exchange=args.exchange,
    )
    plan = build_dataset_plan(request, args.data_source if args.data_source_explicit else None,
                              page_index_explicit=args.page_index_explicit,
                              page_size_explicit=args.page_size_explicit)
    client = InspectorClient(plan.capability.source, timeout=args.timeout)
    results: dict[str, str] = {}
    for number, item in enumerate(plan.requests, 1):
        key = item.label
        try:
            response = client.request_endpoint(plan.endpoint, item.params)
            results[key] = print_report(
                plan.capability.source, plan.endpoint, item.params, response,
                limit=args.limit, full_json=args.full_json, client=client,
                show_mapping=args.show_mapping, dataset=dataset,
                requested_source=args.data_source if args.data_source_explicit else None,
                source_status=plan.capability.status,
                request_number=number, request_count=len(plan.requests),
                request_label=item.label, paging_supported=plan.paging_supported,
            )
        except (InspectorError, ParameterError, MappingConfigurationError, ValueError) as exc:
            results[key] = "FAILED"
            print(f"\n{dataset} request {number}/{len(plan.requests)} ({item.label}) FAILED: "
                  f"{scrub_text(str(exc), [client.token] if client.token else [])}")
    return results


def _validate_endpoint_options(source: str, endpoint: Any, args: argparse.Namespace) -> None:
    supplied = {
        "symbol": args.symbol, "board": args.board, "market": args.market,
        "exchange": args.exchange, "index_code": args.index_code,
        "date": args.date, "from_date": args.from_date, "to_date": args.to_date,
        "ascending": args.ascending,
    }
    v3_allowed = {
        "access-token": set(),
        "securities-by-board": {"symbol", "board", "index_code"},
        "securities-summary": {"symbol", "index_code", "date", "from_date", "to_date"},
        "index-list": {"board", "exchange"},
        "index-summary": {"board", "index_code", "date"},
        "daily-ohlc": {"symbol", "date", "from_date", "to_date", "ascending"},
        "intraday-ohlc": {"symbol", "date", "from_date", "to_date", "ascending"},
        "master-data": {"date", "from_date", "to_date"},
        "securities": {"board", "market"},
        "securities-details": {"symbol"},
        "index-components": {"index_code"},
        "daily-stock-price": {"symbol", "date", "from_date", "to_date"},
        "daily-index": {"index_code", "date"},
    }
    if source != "ssi_v3":
        return  # Legacy builders retain their established compatibility contract.
    unsupported = ["--" + key.replace("_", "-") for key, value in supplied.items()
                   if value is not None and key not in v3_allowed[endpoint.name]]
    if unsupported:
        raise ParameterError(f"{endpoint.name} does not support: {', '.join(unsupported)}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    args = parser.parse_args(raw_argv)
    args.data_source_explicit = "--data-source" in raw_argv
    requested_source = args.data_source if args.data_source_explicit else None
    selected_source = args.data_source
    endpoints = registry(selected_source)
    if args.command == "list":
        print("Canonical datasets (selection is registry-order based; preview is inspector-only):")
        for dataset, capability, endpoint_name in canonical_capabilities():
            if requested_source is None or capability.source == requested_source:
                print(f"{dataset.replace('_', '-')}\t{dataset}\t{capability.source}\t{capability.status}\t{endpoint_name}")
        print(f"\nEndpoint compatibility view — data source: {selected_source}")
        native = [endpoint for endpoint in endpoints.values() if not endpoint.alias_for]
        aliases = [endpoint for endpoint in endpoints.values() if endpoint.alias_for]
        print("Native endpoints:")
        for endpoint in native:
            print(f"{endpoint.name}\t{endpoint.method}\t{endpoint.url}")
        print("Compatibility aliases:")
        if not aliases:
            print("(none; v2 names are native legacy contracts)")
        for endpoint in aliases:
            print(f"{endpoint.name}\t{endpoint.method}\t{endpoint.url}\talias-for={endpoint.alias_for}")
        return 0
    args.page_index_explicit = args.page_index is not None
    args.page_size_explicit = args.page_size is not None
    args.page_index = args.page_index or 1
    args.page_size = args.page_size or 10
    _validate_numeric(parser, args)
    print("READ-ONLY — NO DATABASE WRITES")
    if args.endpoint in CLI_DATASETS:
        try:
            results = run_dataset(args)
        except (ParameterError, MappingConfigurationError, ValueError) as exc:
            parser.error(str(exc))
        print("\nSummary:")
        for name, status in results.items():
            print(f"{name}: {status}")
        return 1 if "FAILED" in results.values() else 0
    if args.endpoint != "all" and args.endpoint not in endpoints:
        parser.error(f"endpoint {args.endpoint!r} is not supported by {selected_source}; no cross-source fallback")
    client = InspectorClient(selected_source, timeout=args.timeout)
    names = RUN_ALL_ORDER[selected_source] if args.endpoint == "all" else [args.endpoint]
    results: dict[str, str] = {}
    for name in names:
        try:
            results[name] = run_one(client, selected_source, name, args)
        except (InspectorError, ParameterError, MappingConfigurationError) as exc:
            results[name] = "FAILED"
            print(f"\n{name} FAILED: {scrub_text(str(exc), [client.token] if client.token else [])}")
    print("\nSummary:")
    for name, status in results.items():
        print(f"{name}: {status}")
    return 1 if "FAILED" in results.values() else 0


if __name__ == "__main__":
    raise SystemExit(main())
