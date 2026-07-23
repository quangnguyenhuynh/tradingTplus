#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from src.pipeline.ingest_check import check_ingest

def main(argv=None):
    parser = argparse.ArgumentParser(description="Check ingest completeness")
    parser.add_argument("--date", required=True)
    parser.add_argument("--symbols", nargs="+", default=None)
    args = parser.parse_args(argv)
    print(json.dumps(check_ingest(args.date, symbols=args.symbols), ensure_ascii=False, indent=2, default=str))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
