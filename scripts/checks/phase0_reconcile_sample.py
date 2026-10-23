#!/usr/bin/env python3
"""Read-only Phase 0 payload and bounded sample reconciliation."""
from __future__ import annotations
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.database.client import SupabaseClient
from src.quality.validators.phase0 import check_intraday_payload, reconcile_sample, validate_reconciliation_scope


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Check a bounded Phase 0 raw/clean/feature sample without writes.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--date", required=True, help="Trading date YYYY-MM-DD")
    parser.add_argument("--timeframe", required=True, choices=("1m", "1d", "15m", "60m"))
    parser.add_argument("--timestamp", help="Exact aware 1m candle or higher-timeframe feature bucket instant; no nearby match")
    parser.add_argument("--tolerance", type=float, default=1e-6)
    args = parser.parse_args(argv)
    try:
        selected = date.fromisoformat(args.date)
        args.symbol = validate_reconciliation_scope(args.symbol, selected, args.timeframe, args.timestamp, args.tolerance)
    except ValueError as exc:
        parser.error(str(exc))
    client = SupabaseClient().get()
    output = {
        "payload": check_intraday_payload(client, symbol=args.symbol, trading_date=selected),
        "reconciliation": reconcile_sample(client, symbol=args.symbol, trading_date=selected,
                                             timeframe=args.timeframe, timestamp=args.timestamp,
                                             tolerance=args.tolerance),
        "read_only": True,
    }
    print(json.dumps(output, indent=2, default=str))
    # Payload presence is informational: daily and exact 1m reconciliation do
    # not depend on an unrelated newest payload sample elsewhere in the day.
    statuses = {output["reconciliation"]["status"]}
    raise SystemExit(1 if "FAIL" in statuses else (2 if "UNKNOWN" in statuses else 0))


if __name__ == "__main__":
    main()
