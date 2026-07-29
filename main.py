#!/usr/bin/env python3
"""TradingTPlus production CLI.

Production commands:
  python main.py sync-master-data
  python main.py init
  python main.py daily [DD/MM/YYYY]
  python main.py intraday-ingest [DD/MM/YYYY] [--symbols SSI HPG]
  python main.py eod [DD/MM/YYYY]
  python main.py backfill-daily --from DD/MM/YYYY --to DD/MM/YYYY
  python main.py backfill-intraday --from DD/MM/YYYY --to DD/MM/YYYY
  python main.py backfill --from DD/MM/YYYY --to DD/MM/YYYY
  python main.py features-daily (--date DD/MM/YYYY | --from DD/MM/YYYY --to DD/MM/YYYY | --mode full)
  python main.py features-intraday (--date DD/MM/YYYY | --from DD/MM/YYYY --to DD/MM/YYYY | --mode full)
  python main.py features [--date DD/MM/YYYY] [--symbols SSI HPG] [--timeframes 15m 60m 1d]
  python main.py intraday [--symbols SSI HPG] [--timeframes 15m 60m]
  python main.py streaming-ingest --symbols SSI --indexes VNINDEX --channels quote --timeout 60 --max-messages-per-channel 1 [--write]

Feature persistence policy:
- stock_intraday keeps canonical 1m source candles;
- the features table persists only 1d, 15m, and 60m;
- 1m and 5m feature writes are rejected.

Exit codes: 0=OK/PARTIAL, 1=FAILED, 2=invalid arguments.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from src.features import (
    DEFAULT_PERSISTED_FEATURE_TIMEFRAMES,
    PERSISTED_INTRADAY_TIMEFRAMES,
    run_daily_feature_backfill,
    run_daily_features_with_summary,
    run_feature_engine_with_summary,
    run_intraday_feature_backfill,
    run_intraday_features_with_summary,
)
from src.pipeline import (
    daily_run,
    init_symbols,
    run_backfill_pipeline,
    run_daily_backfill_pipeline,
    run_eod_pipeline,
    run_intraday_backfill_pipeline,
    run_intraday_ingest,
    run_intraday_pipeline,
    run_streaming_ingest,
)
from src.pipeline.symbol_scope import normalize_symbol_scope


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

    daily = sub.add_parser(
        "daily",
        help="Daily SSI ingest only; no features/signals/backtests",
    )
    daily.add_argument(
        "date",
        nargs="?",
        help="Trading date DD/MM/YYYY; defaults to latest previous weekday",
    )
    daily.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="Stock symbols to ingest; omitted means all master symbols",
    )

    intraday_ingest = sub.add_parser(
        "intraday-ingest",
        help="Production SSI IntradayOhlc 1m ingest only; no features/signals/backtests",
    )
    intraday_ingest.add_argument(
        "date",
        nargs="?",
        help="Trading date DD/MM/YYYY; defaults to latest previous weekday",
    )
    intraday_ingest.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="Symbols to ingest; omitted means all master symbols",
    )

    eod = sub.add_parser(
        "eod",
        help="EOD orchestrator: daily ingest + intraday ingest + completeness validation only; no features",
    )
    eod.add_argument(
        "date",
        nargs="?",
        help="Trading date DD/MM/YYYY; defaults to latest previous weekday",
    )
    eod.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="Stock symbols for daily, intraday, and completeness; omitted means all master symbols",
    )

    for command, help_text in (
        (
            "backfill-daily",
            "Inclusive daily-only source-data backfill; no completeness/features/signals/backtests",
        ),
        (
            "backfill-intraday",
            "Inclusive 1m intraday-only source-data backfill; no daily/completeness/features/signals/backtests",
        ),
        (
            "backfill",
            "Inclusive daily + intraday source-data backfill with completeness; no features/signals/backtests",
        ),
    ):
        command_parser = sub.add_parser(command, help=help_text)
        command_parser.add_argument(
            "--from",
            "--from-date",
            dest="from_date",
            required=True,
            help="Inclusive start date DD/MM/YYYY",
        )
        command_parser.add_argument(
            "--to",
            "--to-date",
            dest="to_date",
            required=True,
            help="Inclusive end date DD/MM/YYYY",
        )
        command_parser.add_argument(
            "--symbols",
            nargs="+",
            default=None,
            help="Stock symbols used for every date; omitted means all master symbols",
        )

    features = sub.add_parser(
        "features",
        help="Compatibility feature router; persists only 1d, 15m, and 60m",
    )
    features.add_argument(
        "--mode",
        choices=["incremental", "full"],
        default="incremental",
    )
    features.add_argument(
        "--date",
        default=None,
        help="Target date DD/MM/YYYY for incremental mode",
    )
    features.add_argument(
        "--symbols",
        nargs="*",
        default=None,
        help="Symbols to process; omitted means all symbols",
    )
    features.add_argument(
        "--timeframes",
        nargs="*",
        default=list(DEFAULT_PERSISTED_FEATURE_TIMEFRAMES),
        help="Persisted feature timeframes: 15m 60m 1d",
    )

    features_daily = sub.add_parser(
        "features-daily",
        help="Explicit stock_daily-only 1d feature pipeline",
    )
    features_daily.add_argument(
        "--mode",
        choices=["incremental", "full"],
        default="incremental",
    )
    features_daily.add_argument(
        "--date",
        default=None,
        help="Target date for incremental mode",
    )
    features_daily.add_argument(
        "--from",
        "--from-date",
        dest="from_date",
        default=None,
        help="Inclusive range start date DD/MM/YYYY",
    )
    features_daily.add_argument(
        "--to",
        "--to-date",
        dest="to_date",
        default=None,
        help="Inclusive range end date DD/MM/YYYY",
    )
    features_daily.add_argument("--symbols", nargs="*", default=None)

    features_intraday = sub.add_parser(
        "features-intraday",
        help="Explicit closed-candle 15m/60m feature pipeline from clean 1m source",
    )
    features_intraday.add_argument(
        "--mode",
        choices=["incremental", "full"],
        default="incremental",
    )
    features_intraday.add_argument(
        "--date",
        default=None,
        help="Target date for incremental mode",
    )
    features_intraday.add_argument(
        "--from",
        "--from-date",
        dest="from_date",
        default=None,
        help="Inclusive range start date DD/MM/YYYY",
    )
    features_intraday.add_argument(
        "--to",
        "--to-date",
        dest="to_date",
        default=None,
        help="Inclusive range end date DD/MM/YYYY",
    )
    features_intraday.add_argument("--symbols", nargs="*", default=None)
    features_intraday.add_argument(
        "--timeframes",
        nargs="*",
        default=list(PERSISTED_INTRADAY_TIMEFRAMES),
        help="Persisted intraday feature timeframes: 15m 60m",
    )
    features_intraday.add_argument(
        "--as-of",
        default=None,
        help="Safe cutoff: HH:MM Vietnam time or timezone-aware timestamp",
    )

    intraday = sub.add_parser(
        "intraday",
        help="Legacy alias for incremental 15m/60m feature calculation; does not ingest candles",
    )
    intraday.add_argument(
        "--snapshot-time",
        default=None,
        help="Optional snapshot marker; defaults to current VN time",
    )
    intraday.add_argument(
        "--symbols",
        nargs="*",
        default=None,
        help="Symbols to process; omitted means all symbols",
    )
    intraday.add_argument(
        "--timeframes",
        nargs="*",
        default=list(PERSISTED_INTRADAY_TIMEFRAMES),
        help="Persisted intraday feature timeframes: 15m 60m",
    )

    streaming = sub.add_parser(
        "streaming-ingest",
        help="Bounded SSI streaming ingest; dry-run/read-only unless --write is passed",
    )
    streaming.add_argument(
        "--symbols",
        nargs="*",
        default=[],
        help="Explicit symbols; never defaults to ALL",
    )
    streaming.add_argument(
        "--indexes",
        nargs="*",
        default=[],
        help="Explicit index codes for index channel",
    )
    streaming.add_argument(
        "--channels",
        nargs="*",
        required=True,
        choices=[
            "securities-status",
            "quote",
            "trade",
            "foreign-room",
            "index",
            "realtime-bar",
        ],
        help="Streaming channel groups to subscribe",
    )
    streaming.add_argument("--timeout", type=int, default=60)
    streaming.add_argument("--max-messages-per-channel", type=int, default=1)
    streaming.add_argument(
        "--write",
        action="store_true",
        default=False,
        help="Persist raw and valid clean rows; omitted means dry-run/read-only",
    )
    streaming.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Print sanitized debug summaries only",
    )
    return parser


def _feature_execution_scope(args: argparse.Namespace) -> str:
    """Validate and identify the requested single-date, range, or full run."""
    has_from = args.from_date is not None
    has_to = args.to_date is not None
    if has_from != has_to:
        raise ValueError("--from and --to must be provided together")
    has_range = has_from and has_to
    if args.date is not None and has_range:
        raise ValueError("--date cannot be combined with --from/--to")
    if args.mode == "full" and (args.date is not None or has_range):
        raise ValueError("--mode full cannot be combined with --date or --from/--to")
    if getattr(args, "as_of", None) is not None and has_range:
        raise ValueError("--as-of cannot be used with a date range")
    if args.mode == "full":
        return "full"
    if has_range:
        return "range"
    if args.date is not None:
        return "date"
    raise ValueError("incremental mode requires --date or --from/--to")


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
            summary = daily_run(
                args.date,
                symbols=normalize_symbol_scope(args.symbols),
            )
            _print_summary(summary)
            return _status_to_exit(summary)
        if args.command == "intraday-ingest":
            summary = run_intraday_ingest(
                args.date,
                symbols=normalize_symbol_scope(args.symbols),
            )
            _print_summary(summary)
            return _status_to_exit(summary)
        if args.command == "eod":
            summary = run_eod_pipeline(
                args.date,
                symbols=normalize_symbol_scope(args.symbols),
            )
            _print_summary(summary)
            return _status_to_exit(summary)
        if args.command in {"backfill-daily", "backfill-intraday", "backfill"}:
            runner = {
                "backfill-daily": run_daily_backfill_pipeline,
                "backfill-intraday": run_intraday_backfill_pipeline,
                "backfill": run_backfill_pipeline,
            }[args.command]
            summary = runner(
                args.from_date,
                args.to_date,
                symbols=normalize_symbol_scope(args.symbols),
            )
            _print_summary(summary)
            return _status_to_exit(summary)
        if args.command == "features":
            summary = run_feature_engine_with_summary(
                symbols=normalize_symbol_scope(args.symbols),
                mode=args.mode,
                timeframes=tuple(args.timeframes),
                target_date=args.date,
            )
            _print_summary(summary)
            return _status_to_exit(summary)
        if args.command == "features-daily":
            scope = _feature_execution_scope(args)
            symbols = normalize_symbol_scope(args.symbols)
            if scope == "range":
                summary = run_daily_feature_backfill(
                    args.from_date,
                    args.to_date,
                    symbols=symbols,
                )
            else:
                summary = run_daily_features_with_summary(
                    symbols=symbols,
                    mode=args.mode,
                    target_date=args.date,
                )
            _print_summary(summary)
            return _status_to_exit(summary)
        if args.command == "features-intraday":
            scope = _feature_execution_scope(args)
            symbols = normalize_symbol_scope(args.symbols)
            timeframes = tuple(args.timeframes)
            if scope == "range":
                summary = run_intraday_feature_backfill(
                    args.from_date,
                    args.to_date,
                    symbols=symbols,
                    timeframes=timeframes,
                )
            else:
                summary = run_intraday_features_with_summary(
                    symbols=symbols,
                    mode=args.mode,
                    timeframes=timeframes,
                    target_date=args.date,
                    as_of=args.as_of,
                )
            _print_summary(summary)
            return _status_to_exit(summary)
        if args.command == "intraday":
            summary = run_intraday_pipeline(
                snapshot_time=args.snapshot_time,
                symbols=normalize_symbol_scope(args.symbols),
                timeframes=tuple(args.timeframes),
            )
            _print_summary(summary)
            return _status_to_exit(summary)
        if args.command == "streaming-ingest":
            summary = run_streaming_ingest(
                symbols=[symbol.upper() for symbol in args.symbols],
                indexes=[index.upper() for index in args.indexes],
                channels=list(args.channels),
                timeout_sec=args.timeout,
                max_messages_per_channel=args.max_messages_per_channel,
                write=args.write,
                debug=args.debug,
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
