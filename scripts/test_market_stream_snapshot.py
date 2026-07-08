#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.client import SupabaseClient
from src.pipeline.streaming_snapshot import (
    build_foreign_snapshot_record,
    build_index_snapshot_record,
    build_quote_snapshot_record,
    build_raw_stream_record,
    build_trade_snapshot_record,
)
from src.ssi.streaming import SSIStreamingClient, normalize_stream_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect and map SSI market stream snapshots")
    parser.add_argument("symbols", nargs="+", help="Symbols to subscribe")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--indexes", default="VNINDEX,VN30")
    parser.add_argument("--raw", action="store_true", help="Print raw payloads")
    parser.add_argument("--write", action="store_true", help="Write mapped records to DB")
    args = parser.parse_args()

    symbols = [s.upper() for s in args.symbols]
    indexes = [i.strip().upper() for i in args.indexes.split(",") if i.strip()]
    channels = [c for s in symbols for c in (f"X-QUOTE:{s}", f"X-TRADE:{s}", f"R:{s}")] + [f"MI:{i}" for i in indexes]
    client = SSIStreamingClient()
    records = {"raw": [], "quote": [], "trade": [], "foreign": [], "index": []}
    try:
        client.connect()
        latest = client.collect_latest_by_channels(channels, timeout_sec=args.timeout, debug=args.raw)
    finally:
        client.close()

    snap = datetime.now(timezone.utc)
    for channel, payload in latest.items():
        norm = normalize_stream_payload(payload)
        content = norm.get("raw") if isinstance(norm.get("raw"), dict) else payload
        rtype = str(norm.get("RType") or channel.split(":", 1)[0]).upper()
        raw_rec = build_raw_stream_record(channel, content, snap)
        records["raw"].append(raw_rec)
        if args.raw:
            print(f"\n=== RAW {channel} ===")
            print(json.dumps(content, indent=2, ensure_ascii=False, default=str))
        mapped = None
        if rtype in ("X-QUOTE", "QUOTE"):
            mapped = build_quote_snapshot_record(content, snap); key = "quote"
        elif rtype in ("X-TRADE", "TRADE"):
            mapped = build_trade_snapshot_record(content, snap); key = "trade"
        elif rtype == "R":
            mapped = build_foreign_snapshot_record(content, snap); key = "foreign"
        elif rtype == "MI":
            mapped = build_index_snapshot_record(content, snap); key = "index"
        else:
            key = ""
        if mapped and key:
            records[key].append(mapped)
            print(f"\n=== MAPPED {key} {channel} ===")
            print(json.dumps(mapped, indent=2, ensure_ascii=False, default=str))

    if args.write:
        db = SupabaseClient()
        db.upsert_stream_raw(records["raw"])
        db.upsert_stream_quote(records["quote"])
        db.upsert_stream_trade(records["trade"])
        db.upsert_stream_foreign_snapshot(records["foreign"])
        db.upsert_stream_index_snapshot(records["index"])

    summary = {key: len(value) for key, value in records.items()}
    print(f"\nSUMMARY {json.dumps(summary, ensure_ascii=False)} write={args.write}")


if __name__ == "__main__":
    main()
