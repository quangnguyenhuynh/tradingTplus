#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
# Avoid shadowing the stdlib inspect module when this file is executed directly.
if str(SCRIPT_DIR) in sys.path:
    sys.path.remove(str(SCRIPT_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ssi_api_inspector.client import InspectorClient, InspectorError, find_token_paths, redact
from scripts.ssi_api_inspector.endpoints import ENDPOINTS, RUN_ALL_ORDER

LIST_KEYS = ("data", "dataList", "items")


def _data_location(body: Any) -> tuple[str | None, list[Any]]:
    if isinstance(body, dict):
        for key in LIST_KEYS:
            if isinstance(body.get(key), list):
                return key, body[key]
        for key, value in body.items():
            if isinstance(value, list):
                return str(key), value
    if isinstance(body, list):
        return "$", body
    return None, []


def _print_json(value: Any) -> None:
    print(json.dumps(redact(value), indent=2, ensure_ascii=False, default=str))


def print_report(endpoint: Any, params: dict[str, Any], response: Any, *, limit: int, full_json: bool) -> str:
    safe_body = redact(response.body)
    location, rows = _data_location(response.body)
    status = "PASS" if rows else "EMPTY"
    first_keys = sorted(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
    print("\n" + "=" * 88)
    print(f"Endpoint: {endpoint.label} ({endpoint.name})")
    print(f"Method: {endpoint.method}")
    print(f"URL: {endpoint.url}")
    print(f"Request params: {json.dumps(redact(params), ensure_ascii=False, default=str)}")
    print(f"HTTP status code: {response.status_code}")
    print(f"Elapsed seconds: {response.elapsed_sec:.3f}")
    print(f"Content type: {response.content_type}")
    if isinstance(response.body, dict):
        print(f"Top-level response keys: {sorted(str(k) for k in response.body.keys())}")
        for key in ("status", "message", "responseCode", "totalRecord"):
            if key in response.body:
                print(f"{key}: {redact(response.body.get(key))}")
    else:
        print(f"Top-level response type: {type(response.body).__name__}")
    print(f"Data list location: {location or 'not found'}")
    print(f"Record count in response: {len(rows)}")
    print(f"First record keys: {first_keys}")
    token_paths = find_token_paths(response.body)
    if token_paths:
        print(f"token_detected=true paths={token_paths}")
    if not rows and endpoint.name != "access-token":
        print("⚠️ Empty response. Verify trading date, symbol/index, market/exchange, or SSI envelope shape.")
    sample = rows[: max(0, limit)]
    print(f"Sample records (limit={limit}):")
    _print_json(sample)
    if full_json:
        print("Full raw JSON (redacted):")
        _print_json(safe_body)
    return status


def run_one(client: InspectorClient, name: str, args: argparse.Namespace) -> str:
    endpoint = ENDPOINTS[name]
    params = endpoint.build_params(args)
    post_json = endpoint.post_json(args) if endpoint.post_json else None
    safe_post_json = redact(post_json or {})
    if endpoint.method == "POST":
        print(f"POST JSON keys for {endpoint.label}: {list((post_json or {}).keys())}; sanitized={safe_post_json}")
    response = client.request_endpoint(endpoint, params, post_json)
    return print_report(endpoint, params, response, limit=args.limit, full_json=args.full_json)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only SSI FastConnect Data REST API inspector.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List supported endpoints")
    run = sub.add_parser("run", help="Run one endpoint or all")
    run.add_argument("endpoint", choices=[*ENDPOINTS.keys(), "all"])
    run.add_argument("--symbol", default="SSI")
    run.add_argument("--date", default="10/07/2026", help="DD/MM/YYYY; safe default is a past explicit date")
    run.add_argument("--market", default="HOSE")
    run.add_argument("--exchange", default="HOSE")
    run.add_argument("--index-code", default="VNINDEX")
    run.add_argument("--page-index", type=int, default=1)
    run.add_argument("--page-size", type=int, default=10)
    run.add_argument("--limit", type=int, default=3)
    run.add_argument("--full-json", action="store_true")
    run.add_argument("--timeout", type=int, default=30)
    run.add_argument("--ascending", action="store_true", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "list":
        for endpoint in ENDPOINTS.values():
            print(f"{endpoint.name}\t{endpoint.method}\t{endpoint.label}\t{endpoint.url}")
        return 0
    client = InspectorClient(timeout=args.timeout)
    names = RUN_ALL_ORDER if args.endpoint == "all" else [args.endpoint]
    results: dict[str, str] = {}
    for name in names:
        try:
            results[name] = run_one(client, name, args)
        except InspectorError as exc:
            results[name] = "FAILED"
            print(f"\n❌ {name} FAILED: {exc}")
    print("\nSummary:")
    for name, status in results.items():
        print(f"{name}: {status}")
    return 1 if any(status == "FAILED" for status in results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
