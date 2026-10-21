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
    parser = argparse.ArgumentParser(description="Snapshot orderbook manually")
    parser.add_argument("symbols", nargs="*")
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument("--debug", action="store_true")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true", default=False)
    group.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(CapabilityUnavailableError("streaming").as_summary()))
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
