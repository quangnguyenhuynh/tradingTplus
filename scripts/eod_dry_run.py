#!/usr/bin/env python3
"""CLI wrapper for read-only SSI EOD ingest + feature dry run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.pipeline.eod_dry_run import DEFAULT_SYMBOLS, DEFAULT_TIMEFRAMES, run_eod_dry_run  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run read-only SSI EOD ingest + feature dry run")
    parser.add_argument("--date", default=None, help="Trading date in DD/MM/YYYY. Defaults to latest previous weekday.")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS, help="Symbols to fetch. Default: SSI")
    parser.add_argument("--timeframes", nargs="+", default=DEFAULT_TIMEFRAMES, help="Feature timeframes. Default: 1m 5m 15m")
    parser.add_argument("--json", action="store_true", help="Print JSON summary instead of pretty CLI output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_eod_dry_run(
        date=args.date,
        symbols=args.symbols,
        timeframes=args.timeframes,
        json_output=args.json,
    )


if __name__ == "__main__":
    main()
