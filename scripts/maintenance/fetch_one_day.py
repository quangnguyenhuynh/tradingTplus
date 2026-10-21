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

def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch/test one symbol for one day")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--date", required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True)
    group.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(CapabilityUnavailableError("stock_intraday").as_summary()))
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
