#!/usr/bin/env python3
"""TradingTPlus production CLI.

Production commands:
  python main.py sync-master-data
  python main.py init
  python main.py daily [DD/MM/YYYY]
  python main.py intraday-ingest [DD/MM/YYYY] [--symbols SSI HPG]
  python main.py eod [DD/MM/YYYY]
  python main.py features [--date DD/MM/YYYY] [--symbols SSI HPG] [--timeframes 1m 5m 15m 60m 1d]
  python main.py intraday [--symbols SSI HPG] [--timeframes 1m 5m 15m]

Exit codes: 0=OK/PARTIAL, 1=FAILED, 2=invalid arguments.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from src.pipeline import init_symbols, daily_run, run_eod_pipeline, run_intraday_pipeline, run_intraday_ingest
from src.engine.feature_engine import run_feature_engine_with_summary


def _status_to_exit(summary: dict[str, Any]) -> int:
    return 1 if summary.get("status") == "FAILED" else 0


def _print_summary(summary: Any) -> None:
    if isinstance(summary, dict):
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TradingTPlus production flows")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sync-master-data", help="Sync SSI master data into DB")
    sub.add_parser("init", help="Alias for sync-master-data")

    daily = sub.add_parser("daily", help="Daily SSI ingest only; no features/signals/backtests")
    daily.add_argument("date", nargs="?", help="Trading date DD/MM/YYYY; defaults to latest previous weekday")

    intraday_ingest = sub.add_parser("intraday-ingest", help="Production SSI IntradayOhlc 1m ingest only; no features/signals/backtests")
    intraday_ingest.add_argument("date", nargs="?", help="Trading date DD/MM/YYYY; defaults to latest previous weekday")
    intraday_ingest.add_argument("--symbols", nargs="*", default=None, help="Symbols to ingest; omitted means all active symbols")

    eod = sub.add_parser("eod", help="EOD orchestrator: daily ingest + intraday ingest + completeness validation only; no features")
    eod.add_argument("date", nargs="?", help="Trading date DD/MM/YYYY; defaults to latest previous weekday")

    features = sub.add_parser("features", help="Explicit feature pipeline; supports target date reruns/backfills")
    features.add_argument("--mode", choices=["incremental", "full"], default="incremental")
    features.add_argument("--date", default=None, help="Target date DD/MM/YYYY for incremental mode")
    features.add_argument("--symbols", nargs="*", default=None, help="Symbols to process; omitted means all symbols")
    features.add_argument("--timeframes", nargs="*", default=None, help="Feature timeframes: 1m 5m 15m 60m 1d")

    intraday = sub.add_parser("intraday", help="Legacy alias for `features --mode incremental --timeframes 1m 5m 15m`; does not ingest candles")
    intraday.add_argument("--snapshot-time", default=None, help="Optional snapshot marker; defaults to current VN time")
    intraday.add_argument("--symbols", nargs="*", default=None, help="Symbols to process; omitted means all symbols")
    intraday.add_argument("--timeframes", nargs="*", default=["1m", "5m", "15m"], help="Intraday feature timeframes")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code else 0

    try:
        if args.command in {"init", "sync-master-data"}:
            init_symbols()
            return 0
        if args.command == "daily":
            summary = daily_run(args.date)
            _print_summary(summary)
            return _status_to_exit(summary)
        if args.command == "intraday-ingest":
            symbols = [s.upper() for s in args.symbols] if args.symbols else None
            summary = run_intraday_ingest(args.date, symbols=symbols)
            _print_summary(summary)
            return _status_to_exit(summary)
        if args.command == "eod":
            summary = run_eod_pipeline(args.date)
            _print_summary(summary)
            return _status_to_exit(summary)
        if args.command == "features":
            symbols = [s.upper() for s in args.symbols] if args.symbols else None
            summary = run_feature_engine_with_summary(
                symbols=symbols,
                mode=args.mode,
                timeframes=tuple(args.timeframes) if args.timeframes else None,
                target_date=args.date,
            )
            _print_summary(summary)
            return _status_to_exit(summary)
        if args.command == "intraday":
            symbols = [s.upper() for s in args.symbols] if args.symbols else None
            summary = run_intraday_pipeline(
                snapshot_time=args.snapshot_time,
                symbols=symbols,
                timeframes=tuple(args.timeframes),
            )
            _print_summary(summary)
            return _status_to_exit(summary)
        parser.error(f"Unsupported command: {args.command}")
    except ValueError as exc:
        print(f"❌ Invalid arguments: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"❌ {args.command} failed: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
