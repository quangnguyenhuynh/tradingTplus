#!/usr/bin/env python
"""Debug SSI Streaming X-QUOTE orderbook payloads.

Default mode is read-only: login SSI, connect streaming, subscribe X-QUOTE for
symbols, print raw quote payload and mapped orderbook_snapshot record. Pass
--write to upsert one snapshot per symbol.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import config
from src.database.client import SupabaseClient
from src.pipeline.orderbook_snapshot import build_orderbook_record
from src.ssi.streaming import SSIStreamingQuoteClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only debug for SSI Streaming X-QUOTE orderbook snapshots.")
    parser.add_argument("symbols", nargs="+", help="Symbols to subscribe, e.g. SSI HPG FPT, or ALL")
    parser.add_argument("--timeout-sec", type=int, default=config.ORDERBOOK_SNAPSHOT_TIMEOUT_SEC)
    parser.add_argument("--write", action="store_true", help="Upsert mapped orderbook_snapshot rows to Supabase")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbols = [symbol.upper() for symbol in args.symbols]
    print("🔎 SSI Streaming X-QUOTE orderbook debug")
    print(f"symbols: {symbols}")
    print(f"timeout_sec: {args.timeout_sec}")
    print(f"write: {args.write}")
    client = SSIStreamingQuoteClient(timeout_sec=args.timeout_sec)
    try:
        client.connect()
        client.subscribe_quote("ALL" if symbols == ["ALL"] else symbols)
        targets = symbols if symbols != ["ALL"] else []
        if not targets:
            raise SystemExit("❌ Debug --write/mapper needs concrete symbols; pass symbols instead of ALL for snapshot mapping.")
        latest = client.collect_latest_quotes(targets, timeout_sec=args.timeout_sec, debug=True)
    finally:
        client.close()
    now = datetime.now(timezone.utc)
    records = []
    for symbol in targets:
        quote = latest.get(symbol)
        print("\n" + "=" * 80)
        print(f"SYMBOL {symbol}")
        print("=" * 80)
        print("raw quote:")
        print(json.dumps(quote, indent=2, ensure_ascii=False, default=str))
        record = build_orderbook_record(symbol, quote, now)
        print("mapped orderbook_snapshot:")
        print(json.dumps(record, indent=2, ensure_ascii=False, default=str))
        if record:
            records.append(record)
    if args.write:
        if records:
            SupabaseClient().upsert_orderbook(records)
        print(f"✅ Wrote orderbook_snapshot rows: {len(records)}")
    else:
        print("✅ Read-only debug completed; no DB writes attempted. Pass --write to persist.")


if __name__ == "__main__":
    main()
