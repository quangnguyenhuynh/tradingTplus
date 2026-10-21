#!/usr/bin/env python3
"""Unavailable diagnostic; argument parsing is retained, network and DB access disabled."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.providers.ssi.capabilities import CapabilityUnavailableError
DEFAULT_SYMBOLS = ["SSI", "HPG", "FPT"]
DEFAULT_TIMEFRAMES = ["15m", "60m", "1d"]
from scripts.inspectors.ssi_streaming.registry import STREAM_TYPES

def build_parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="Unavailable streaming inspector; no connection implementation.")
    sub=p.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    neg=sub.add_parser("negotiate"); neg.add_argument("--timeout", type=int, default=30)
    run=sub.add_parser("run"); run.add_argument("kind", choices=[*STREAM_TYPES.keys(), "all"]); run.add_argument("--symbols", nargs="+", default=["SSI"]); run.add_argument("--index-codes", nargs="+", default=["VNINDEX"]); run.add_argument("--timeout", type=int, default=30); run.add_argument("--max-messages", type=int, default=3); run.add_argument("--limit", type=int, default=None); run.add_argument("--full-json", action="store_true"); run.add_argument("--raw-frames", action="store_true"); run.add_argument("--channel"); run.add_argument("--negotiate-only", action="store_true")
    return p

def main(argv=None):
    args = build_parser().parse_args(argv)
    print(json.dumps(CapabilityUnavailableError("streaming").as_summary()))
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
