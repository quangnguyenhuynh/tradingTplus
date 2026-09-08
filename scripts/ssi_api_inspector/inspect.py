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
from scripts.ssi_api_inspector.endpoints import (DATA_SOURCES, RUN_ALL_ORDER,
                                                  ParameterError, registry)

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
    success = _lookup(body, "success")
    if success is False:
        return str(_lookup(body, "message") or "success=false")
    error = _lookup(body, "error")
    if error not in (None, "", False, [], {}):
        return str(error)
    status = _lookup(body, "status")
    if isinstance(status, str) and status.lower() in {"error", "failed", "failure"}:
        return str(_lookup(body, "message") or status)
    code = _lookup(body, "responseCode")
    if code is not None and str(code).strip().lower() not in {"0", "00", "200", "success", "ok"}:
        return str(_lookup(body, "message") or f"responseCode={code}")
    return None


def _safe_url(url: str) -> str:
    parts = urlsplit(url)
    query = [(key, "[REDACTED]" if any(p in key.replace("_", "").lower() for p in ("token", "secret", "apikey", "consumerid")) else value)
             for key, value in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _print_json(value: Any) -> None:
    print(json.dumps(redact(value), indent=2, ensure_ascii=False, default=str))


def print_report(source: str, endpoint: Any, params: dict[str, Any], response: Any,
                 *, limit: int, full_json: bool, client: InspectorClient | None = None) -> str:
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
    print(f"Paging metadata (provider-reported): {json.dumps(redact(paging), ensure_ascii=False, default=str)}")
    first_keys = sorted(str(key) for key in rows[0]) if rows and isinstance(rows[0], dict) else []
    print(f"First record keys: {first_keys}")
    token_paths = find_token_paths(response.body)
    if token_paths:
        print(f"Sensitive fields detected and redacted: {token_paths}")
    print(f"Status: {status}")
    if error:
        print(f"API error: {scrub_text(error, [client.token] if client and client.token else [])}")
    print(f"Sample records (limit={limit}):")
    _print_json((rows or [])[:max(0, limit)])
    if full_json:
        if response.json_state == "json":
            print("Full raw JSON (redacted only; no mapper):")
            _print_json(response.body)
        else:
            print("Full raw response text (redacted):")
            print(scrub_text(response.text, [client.token] if client and client.token else []))
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
    params = endpoint.build_params(endpoint_args)
    post_json = endpoint.post_json(endpoint_args) if endpoint.post_json else None
    response = client.request_endpoint(endpoint, params, post_json)
    return print_report(source, endpoint, params, response, limit=args.limit,
                        full_json=args.full_json, client=client)


def _add_source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-source", choices=DATA_SOURCES, default="ssi_v3",
                        help="SSI REST source (default: ssi_v3; ssi_v2 is legacy and explicit)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only SSI REST API inspector (v3 by default).")
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="List endpoints for one source; no credentials/network required")
    _add_source(listing)
    run = sub.add_parser("run", help="Run one endpoint or all data endpoints")
    run.add_argument("endpoint", help="Endpoint name, compatibility alias, or 'all'")
    _add_source(run)
    run.add_argument("--symbol")
    run.add_argument("--date", help="One date in DD/MM/YYYY or YYYY-MM-DD")
    run.add_argument("--from-date", help="Range start in DD/MM/YYYY or YYYY-MM-DD")
    run.add_argument("--to-date", help="Range end in DD/MM/YYYY or YYYY-MM-DD")
    run.add_argument("--board")
    run.add_argument("--market", help="Compatibility alias for board where supported")
    run.add_argument("--exchange", help="Compatibility alias for board where supported")
    run.add_argument("--index-code")
    run.add_argument("--page-index", type=int, default=1)
    run.add_argument("--page-size", type=int, default=10)
    run.add_argument("--limit", type=int, default=3)
    run.add_argument("--full-json", action="store_true")
    run.add_argument("--timeout", type=int, default=30)
    run.add_argument("--ascending", action="store_true", default=None)
    return parser


def _validate_numeric(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.page_index < 1 or args.page_size < 1 or args.limit < 0 or not 1 <= args.timeout <= 120:
        parser.error("page-index/page-size must be positive, limit non-negative, and timeout 1..120")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    endpoints = registry(args.data_source)
    if args.command == "list":
        print(f"Data source: {args.data_source}" + (" (legacy; select explicitly)" if args.data_source == "ssi_v2" else " (default)"))
        for endpoint in endpoints.values():
            alias = f" alias-for={endpoint.alias_for}" if endpoint.alias_for else ""
            print(f"{endpoint.name}\t{endpoint.method}\t{endpoint.url}{alias}")
        return 0
    _validate_numeric(parser, args)
    if args.endpoint != "all" and args.endpoint not in endpoints:
        parser.error(f"endpoint {args.endpoint!r} is not supported by {args.data_source}; no cross-source fallback")
    client = InspectorClient(args.data_source, timeout=args.timeout)
    names = RUN_ALL_ORDER[args.data_source] if args.endpoint == "all" else [args.endpoint]
    results: dict[str, str] = {}
    for name in names:
        try:
            results[name] = run_one(client, args.data_source, name, args)
        except (InspectorError, ParameterError) as exc:
            results[name] = "FAILED"
            print(f"\n{name} FAILED: {scrub_text(str(exc), [client.token] if client.token else [])}")
    print("\nSummary:")
    for name, status in results.items():
        print(f"{name}: {status}")
    return 1 if "FAILED" in results.values() else 0


if __name__ == "__main__":
    raise SystemExit(main())
