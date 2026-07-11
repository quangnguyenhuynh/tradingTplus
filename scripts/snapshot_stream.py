#!/usr/bin/env python3
from __future__ import annotations
import argparse
from src.database.client import SupabaseClient
from src.pipeline.streaming_snapshot import snapshot_market_stream

def main(argv=None):
    parser = argparse.ArgumentParser(description="Snapshot market stream manually")
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument("--indexes", nargs="*", default=["VNINDEX", "VN30"])
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--write", action="store_true", default=False)
    args = parser.parse_args(argv)
    symbols = [s.upper() for s in args.symbols] if args.symbols else [s.upper() for s in SupabaseClient().get_symbols()[:args.limit]]
    summary = snapshot_market_stream(symbols=symbols[:args.limit] if args.limit else symbols, indexes=[i.upper() for i in args.indexes], timeout_sec=args.timeout, write=args.write, debug=args.debug)
    print(f"Snapshot stream complete: {summary}")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
