#!/usr/bin/env python
"""Explicit, guarded sample backfill runner.

This script writes to Supabase via the production backfill pipeline. It no longer
contains hardcoded symbol/date defaults; pass all targets explicitly.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.backfill import backfill
from src.pipeline.date_utils import parse_iso_date, validate_not_future


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a small explicit backfill sample. Writes to Supabase.")
    parser.add_argument("--from-date", required=True, help="Inclusive start date YYYY-MM-DD")
    parser.add_argument("--to-date", required=True, help="Inclusive end date YYYY-MM-DD")
    parser.add_argument("--symbols", nargs="+", required=True, help="Symbols to backfill, e.g. SSI FPT")
    parser.add_argument("--force", action="store_true", help="Allow future dates after printing warning")
    args = parser.parse_args()

    start = parse_iso_date(args.from_date)
    end = parse_iso_date(args.to_date)
    if start.date > end.date:
        raise SystemExit("❌ --from-date must be <= --to-date")
    if not args.force:
        validate_not_future(start)
        validate_not_future(end)

    symbols = [symbol.upper() for symbol in args.symbols]
    print("⚠️ BACKFILL SAMPLE WRITE CONFIRMATION")
    print(f"   from_date: {start.iso}")
    print(f"   to_date  : {end.iso}")
    print(f"   symbols  : {', '.join(symbols)}")
    print("   No hardcoded/default test date will be used.")
    backfill(start.iso, end.iso, symbols, allow_future=args.force)


if __name__ == "__main__":
    main()
