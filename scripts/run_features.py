#!/usr/bin/env python3
from __future__ import annotations

import argparse

from src.features import (
    DEFAULT_PERSISTED_FEATURE_TIMEFRAMES,
    run_feature_engine,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run persisted feature engine manually")
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="incremental",
    )
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument(
        "--timeframes",
        nargs="*",
        default=list(DEFAULT_PERSISTED_FEATURE_TIMEFRAMES),
        help="Persisted feature timeframes: 15m 60m 1d",
    )
    args = parser.parse_args(argv)
    total = run_feature_engine(
        symbols=[symbol.upper() for symbol in args.symbols]
        if args.symbols
        else None,
        mode=args.mode,
        timeframes=args.timeframes,
    )
    print(f"Feature engine complete: {total} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
