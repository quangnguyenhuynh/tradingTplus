#!/usr/bin/env python3
"""Unavailable diagnostic; argument parsing is retained, network and DB access disabled."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.providers.ssi.capabilities import CapabilityUnavailableError
DEFAULT_SYMBOLS = ["SSI", "HPG", "FPT"]
DEFAULT_TIMEFRAMES = ["15m", "60m", "1d"]

def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only by default smoke test for complete SSI ingest mapping.")
    parser.add_argument("--symbol", default="SSI", help="Symbol to fetch for smoke test; default is SSI and read-only unless --write is passed.")
    parser.add_argument("--date", default=None, help="DD/MM/YYYY. Required when --write is used; read-only mode defaults to latest previous weekday.")
    parser.add_argument("--index-code", default="VNINDEX", help="Index code to fetch for DailyIndex smoke test.")
    parser.add_argument("--write", action="store_true", help="Persist raw_daily, stock_daily, securities, indexes, and index_daily. Disabled by default.")
    parser.add_argument("--write-intraday", action="store_true", help="Also persist raw_intraday and stock_intraday. Requires --write.")
    parser.add_argument("--force", action="store_true", help="Allow writes for weekend or future dates. Still requires explicit --date with --write.")
    return parser.parse_args(argv)

def main(argv=None):
    args = parse_args(argv)
    print(json.dumps(CapabilityUnavailableError("master").as_summary()))
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
