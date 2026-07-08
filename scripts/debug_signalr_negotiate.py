#!/usr/bin/env python
"""Debug raw SSI SignalR negotiate responses without signalrcore/websocket.

This script does not write DB, does not connect websocket, and does not depend on
Supabase. It logs in through the existing SSIApi to get an access token unless
`--no-auth` is passed, then calls SignalR negotiate URLs directly with requests.

Usage:
  python scripts/debug_signalr_negotiate.py
  python scripts/debug_signalr_negotiate.py --method GET
  python scripts/debug_signalr_negotiate.py --no-auth
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import config
from src.ssi.api import SSIApi


def _signalr_url() -> str:
    return urljoin(config.SSI_STREAMING_BASE_URL.rstrip("/") + "/", config.SSI_SIGNALR_PATH.lstrip("/"))


def _negotiate_urls(signalr_url: str) -> list[str]:
    base = signalr_url.rstrip("/") + "/negotiate"
    return [
        base,
        base + "?negotiateVersion=1",
        base + "?clientProtocol=2.1",
    ]


def _headers(token: str | None, *, no_auth: bool) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "tradingTplus-debug/1.0",
    }
    if token and not no_auth:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _print_json_diagnostics(data: Any) -> None:
    print("json parsed:")
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    if not isinstance(data, dict):
        return
    for key in ("error", "Error", "message", "Message", "status", "Status"):
        if key in data:
            print(f"⚠️ response {key}: {data[key]}")
    if "negotiateVersion" in data and not isinstance(data.get("negotiateVersion"), int):
        print(
            "⚠️ negotiateVersion exists but is not int: "
            f"value={data.get('negotiateVersion')!r}, type={type(data.get('negotiateVersion')).__name__}"
        )


def _call_negotiate(method: str, url: str, headers: dict[str, str], timeout: int) -> None:
    print("\n" + "=" * 100)
    print(f"request method: {method}")
    print(f"request url   : {url}")
    print("request headers:")
    safe_headers = {k: ("Bearer ***" if k.lower() == "authorization" else v) for k, v in headers.items()}
    print(json.dumps(safe_headers, indent=2, ensure_ascii=False))
    try:
        response = requests.request(method, url, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        print(f"❌ request failed: {exc}")
        return

    print(f"status_code: {response.status_code}")
    print("response headers:")
    print(json.dumps(dict(response.headers), indent=2, ensure_ascii=False, default=str))
    text = response.text or ""
    print("first 2000 chars response text:")
    print(text[:2000])
    if not text:
        print("⚠️ empty response body")
        return
    try:
        data = response.json()
    except ValueError:
        print("⚠️ response is not JSON; endpoint may be wrong, redirected, blocked, or returning HTML/text.")
        return
    _print_json_diagnostics(data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debug SSI SignalR negotiate raw responses.")
    parser.add_argument("--method", choices=("GET", "POST"), default="POST", help="HTTP method for negotiate calls. Default: POST")
    parser.add_argument("--no-auth", action="store_true", help="Do not include Authorization header; useful for auth comparison.")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds. Default: 30")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    signalr_url = _signalr_url()
    negotiate_urls = _negotiate_urls(signalr_url)
    token: str | None = None
    if not args.no_auth:
        api = SSIApi()
        token = api.token

    print("🔎 SSI SignalR negotiate debug")
    print(f"SSI_STREAMING_BASE_URL: {config.SSI_STREAMING_BASE_URL}")
    print(f"SSI_SIGNALR_PATH      : {config.SSI_SIGNALR_PATH}")
    print(f"full signalr_url      : {signalr_url}")
    print(f"negotiate_url(s)      :")
    for url in negotiate_urls:
        print(f"  - {url}")
    print(f"SSI_SIGNALR_HUB       : {config.SSI_SIGNALR_HUB}")
    print(f"auth                  : {'disabled (--no-auth)' if args.no_auth else 'Authorization: Bearer <token>'}")

    headers = _headers(token, no_auth=args.no_auth)
    for url in negotiate_urls:
        _call_negotiate(args.method, url, headers, args.timeout)


if __name__ == "__main__":
    main()
