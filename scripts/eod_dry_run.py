#!/usr/bin/env python3
from __future__ import annotations
import argparse
from src.pipeline.eod_dry_run import DEFAULT_SYMBOLS, DEFAULT_TIMEFRAMES, run_eod_dry_run

def main(argv=None):
    parser = argparse.ArgumentParser(description="EOD dry-run; read-only")
    parser.add_argument("--date", default=None)
    parser.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)
    parser.add_argument("--timeframes", nargs="*", default=DEFAULT_TIMEFRAMES)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    run_eod_dry_run(date=args.date, symbols=[s.upper() for s in args.symbols], timeframes=args.timeframes, json_output=args.json)
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
