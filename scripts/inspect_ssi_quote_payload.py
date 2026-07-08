#!/usr/bin/env python
"""Inspect an SSI FCData quote/marketdata payload and map bid/ask depth.

The SSI PDF screenshot refers to quote market data messages (RType='X') that
contain BidPrice1/BidVol1...AskPriceN/AskVolN fields. This helper is read-only:
provide a JSON payload from a file or stdin and it prints the mapped
orderbook_snapshot record without writing to Supabase.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.orderbook_snapshot import build_orderbook_record


def _load_payload(path: str | None) -> dict[str, Any]:
    raw_text = Path(path).read_text() if path else sys.stdin.read()
    raw_text = raw_text.strip()
    if not raw_text:
        raise SystemExit("❌ No JSON payload supplied. Pass --file or pipe JSON into stdin.")
    data = json.loads(raw_text)
    if isinstance(data, dict) and isinstance(data.get("content"), str):
        # Some FCData wrappers carry quote JSON as a string in `content`.
        content = data["content"].strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return data
    if not isinstance(data, dict):
        raise SystemExit("❌ Payload must be a JSON object or wrapper with JSON string content.")
    return data


def _infer_symbol(payload: dict[str, Any], fallback: str | None) -> str:
    symbol = payload.get("Symbol") or payload.get("symbol") or fallback
    if not symbol:
        raise SystemExit("❌ Cannot infer symbol from payload; pass --symbol.")
    return str(symbol).upper()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only mapper for SSI FCData quote marketdata payloads.")
    parser.add_argument("--file", help="Path to JSON payload file. If omitted, read from stdin.")
    parser.add_argument("--symbol", help="Fallback symbol if payload does not include Symbol.")
    parser.add_argument("--full-json", action="store_true", help="Print full mapped JSON.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = _load_payload(args.file)
    symbol = _infer_symbol(payload, args.symbol)
    mapped = build_orderbook_record(symbol, payload)
    print("🔎 SSI FCData quote payload inspector (READ-ONLY)")
    print(f"symbol: {symbol}")
    print(f"raw keys: {', '.join(sorted(str(k) for k in payload.keys())[:80])}")
    print(f"mapped orderbook_snapshot: {bool(mapped)}")
    if not mapped:
        print("⚠️ Could not map depth. Check that payload includes BidPrice1/BidVol1 and AskPrice1/AskVol1 style fields.")
        return
    print(f"total_bid_depth_10: {mapped.get('total_bid_depth_10')}")
    print(f"total_ask_depth_10: {mapped.get('total_ask_depth_10')}")
    print(f"orderbook_imbalance: {mapped.get('orderbook_imbalance')}")
    print(f"pressure_score: {mapped.get('pressure_score')}")
    text = json.dumps(mapped, indent=2, ensure_ascii=False, default=str)
    if args.full_json or len(text) <= 5000:
        print(text)
    else:
        print(text[:5000])
        print("... <truncated; pass --full-json to print all>")


if __name__ == "__main__":
    main()
