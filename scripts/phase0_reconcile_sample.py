#!/usr/bin/env python3
"""Read-only Phase 0 payload and bounded sample reconciliation."""
from __future__ import annotations
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.database.client import SupabaseClient
from src.validation.phase0 import check_intraday_payload, reconcile_sample


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a bounded Phase 0 raw/clean/feature sample without writes.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--date", required=True, help="Trading date YYYY-MM-DD")
    parser.add_argument("--timeframe", required=True, choices=("1d", "15m", "60m"))
    parser.add_argument("--timestamp", help="Optional exact feature timestamp for intraday scope")
    parser.add_argument("--tolerance", type=float, default=1e-6)
    args = parser.parse_args()
    selected = date.fromisoformat(args.date)
    client = SupabaseClient().get()
    output = {
        "payload": check_intraday_payload(client, symbol=args.symbol, trading_date=selected),
        "reconciliation": reconcile_sample(client, symbol=args.symbol, trading_date=selected,
                                             timeframe=args.timeframe, timestamp=args.timestamp,
                                             tolerance=args.tolerance),
        "read_only": True,
    }
    print(json.dumps(output, indent=2, default=str))
    statuses = {output["payload"]["status"], output["reconciliation"]["status"]}
    raise SystemExit(1 if "FAIL" in statuses else (2 if "UNKNOWN" in statuses else 0))


if __name__ == "__main__":
    main()
