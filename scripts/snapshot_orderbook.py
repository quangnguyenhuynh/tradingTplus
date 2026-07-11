#!/usr/bin/env python3
from __future__ import annotations
import argparse
from src.pipeline.orderbook_snapshot import snapshot_orderbook_from_stream

def main(argv=None):
    parser = argparse.ArgumentParser(description="Snapshot orderbook manually")
    parser.add_argument("symbols", nargs="*")
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument("--debug", action="store_true")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true", default=False)
    group.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    count = snapshot_orderbook_from_stream(symbols=[s.upper() for s in args.symbols], timeout_sec=args.timeout, write=args.write and not args.no_write, debug=args.debug)
    print(f"Snapshot orderbook complete: {count} records")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
