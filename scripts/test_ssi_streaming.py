#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import config
from src.database.client import SupabaseClient
from src.pipeline.orderbook_snapshot import build_orderbook_record
from src.ssi.streaming import SSIStreamingClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test SSI SignalR streaming X-QUOTE channels.")
    parser.add_argument("symbols", nargs="+", help="Symbols, e.g. SSI HPG FPT")
    parser.add_argument("--timeout", type=int, default=config.ORDERBOOK_SNAPSHOT_TIMEOUT_SEC)
    parser.add_argument("--raw", action="store_true", help="Print raw/parsed/normalized callback samples")
    parser.add_argument("--write", action="store_true", help="Write mapped orderbook_snapshot records to Supabase")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbols = [symbol.upper() for symbol in args.symbols]
    client = SSIStreamingClient()
    print("🔌 SSI SignalR streaming test")
    print(f"Streaming base url: {config.SSI_STREAMING_BASE_URL}")
    print(f"SignalR path: {config.SSI_SIGNALR_PATH}")
    print(f"SignalR URL: {client.signalr_url}")
    print(f"Hub: {config.SSI_SIGNALR_HUB}")
    print(f"Receive method: {config.SSI_SIGNALR_RECEIVE_METHOD}")
    print(f"Switch method: {config.SSI_SIGNALR_SWITCH_METHOD}")
    print(f"Channels: {', '.join('X-QUOTE:' + symbol for symbol in symbols)}")
    try:
        client.connect()
        print("✅ SignalR connected")
        latest = client.collect_latest_quotes(symbols, timeout_sec=args.timeout, debug=args.raw)
    except Exception as exc:
        print("❌ SignalR connect failed or listen failed")
        print(f"URL đang dùng: {client.signalr_url}")
        print(f"Hub đang dùng: {config.SSI_SIGNALR_HUB}")
        print("Gợi ý kiểm tra token/quyền streaming/tài khoản FastConnect")
        print(f"Error: {exc}")
        raise SystemExit(1) from exc
    finally:
        client.close()

    records = []
    for symbol in symbols:
        quote = latest.get(symbol)
        print(f"\n=== {symbol} ===")
        if not quote:
            print(f"⚠️ No quote received within {args.timeout}s")
            continue
        print("Normalized quote:")
        print(json.dumps(quote, indent=2, ensure_ascii=False, default=str))
        record = build_orderbook_record(symbol, quote.get("raw"))
        print("Mapped orderbook record:")
        print(json.dumps(record, indent=2, ensure_ascii=False, default=str))
        if record:
            records.append(record)
            print(f"orderbook_imbalance: {record.get('orderbook_imbalance')}")
    if args.write:
        if records:
            db = SupabaseClient()
            db.upsert_orderbook(records)
            print(f"✅ Wrote orderbook_snapshot rows: {len(records)}")
        else:
            print("⚠️ --write requested but no records were mapped")
    else:
        print("ℹ️ Read-only mode; pass --write to persist mapped snapshots")


if __name__ == "__main__":
    main()
