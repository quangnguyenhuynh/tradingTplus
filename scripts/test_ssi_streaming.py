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
from src.ssi.streaming import SSIStreamingClient, normalize_quote


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test SSI streaming X-QUOTE subscriptions. Read-only by default.")
    parser.add_argument("symbols", nargs="+", help="Symbols, e.g. SSI HPG FPT")
    parser.add_argument("--timeout", type=int, default=config.ORDERBOOK_SNAPSHOT_TIMEOUT_SEC)
    parser.add_argument("--write", action="store_true", help="Write mapped orderbook_snapshot records to Supabase")
    parser.add_argument("--raw", action="store_true", help="Print first raw message")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbols = [symbol.upper() for symbol in args.symbols]
    if not config.SSI_STREAMING_URL:
        raise SystemExit("❌ SSI_STREAMING_URL is not configured")
    print("🔎 SSI streaming test")
    print(f"url: {config.SSI_STREAMING_URL}")
    print(f"symbols: {symbols}")
    print(f"timeout: {args.timeout}")
    print(f"write: {args.write}")
    client = SSIStreamingClient()
    latest = {}
    first_raw_printed = False
    try:
        client.connect()
        channels = [f"X-QUOTE:{symbol}" for symbol in symbols]
        client.subscribe_many(channels)
        for parsed in client.listen(timeout_sec=args.timeout):
            if args.raw and not first_raw_printed:
                print("first raw message:")
                print(parsed.get("raw"))
                first_raw_printed = True
            print("parsed message:")
            print(json.dumps(parsed, indent=2, ensure_ascii=False, default=str)[:5000])
            quote = normalize_quote(parsed)
            print("normalized quote:")
            print(json.dumps(quote, indent=2, ensure_ascii=False, default=str)[:5000])
            if not quote:
                continue
            symbol = str(quote.get("Symbol", "")).upper()
            if symbol in symbols:
                record = build_orderbook_record(symbol, quote)
                print("mapped orderbook record:")
                print(json.dumps(record, indent=2, ensure_ascii=False, default=str)[:5000])
                if record:
                    latest[symbol] = record
            if len(latest) >= len(symbols):
                break
    except Exception as exc:
        raise SystemExit(f"❌ SSI streaming connect/listen failed: {exc}") from exc
    finally:
        client.close()
    if not latest:
        print("No quote received. Check market hours, SSI_STREAMING_URL, token permission, or subscription format.")
        return
    records = list(latest.values())
    if args.write:
        db = SupabaseClient()
        db.upsert_orderbook(records)
        print(f"✅ Wrote orderbook_snapshot records: {len(records)}")
    else:
        print(f"✅ Read-only mapped orderbook records: {len(records)}. Pass --write to persist.")


if __name__ == "__main__":
    main()
