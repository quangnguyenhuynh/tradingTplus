#!/usr/bin/env python3
from __future__ import annotations
import argparse
from src.features.runner import run_feature_engine
from src.features.runtime import DEFAULT_FEATURE_TIMEFRAMES

def main(argv=None):
    parser = argparse.ArgumentParser(description="Run feature engine manually")
    parser.add_argument("--mode", choices=["full", "incremental"], default="incremental")
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument("--timeframes", nargs="*", default=list(DEFAULT_FEATURE_TIMEFRAMES))
    args = parser.parse_args(argv)
    total = run_feature_engine(symbols=[s.upper() for s in args.symbols] if args.symbols else None, mode=args.mode, timeframes=args.timeframes)
    print(f"Feature engine complete: {total} records")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
