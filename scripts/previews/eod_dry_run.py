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
    parser = argparse.ArgumentParser(description="EOD dry-run; read-only")
    parser.add_argument("--date", default=None)
    parser.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)
    parser.add_argument("--timeframes", nargs="*", default=DEFAULT_TIMEFRAMES)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(CapabilityUnavailableError("stock_intraday").as_summary()))
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
