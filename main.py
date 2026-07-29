#!/usr/bin/env python3
"""TradingTPlus production CLI.

Feature commands support three explicit scopes:
- incremental one date: --date DD/MM/YYYY
- inclusive range backfill: --from DD/MM/YYYY --to DD/MM/YYYY
- all history: --mode full

Persisted feature timeframes remain limited to 1d, 15m, and 60m.
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


def _add_range_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--from",
        "--from-date",
        dest="from_date",
        default=None,
        help="Inclusive start date DD/MM/YYYY for range backfill",
    )
    parser.add_argument(
        "--to",
        "--to-date",
        dest="to_date",
        default=None,
        help="Inclusive end date DD/MM/YYYY for range backfill",
    )


def _validate_feature_scope(args) -> str:
    has_date = bool(args.date)
    has_from = bool(args.from_date)
    has_to = bool(args.to_date)
    has_range = has_from or has_to

    if has_from != has_to:
        raise ValueError("--from and --to must be provided together")
    if has_date and has_range:
        raise ValueError("--date cannot be combined with --from/--to")
    if args.mode == "full" and (has_date or has_range):
        raise ValueError("--mode full cannot be combined with --date or --from/--to")
    if getattr(args, "as_of", None) and has_range:
        raise ValueError("--as-of is only valid for a one-date incremental run")
    if args.mode == "incremental" and not has_date and not has_range:
        raise ValueError("incremental feature mode requires --date or --from/--to")
    return "range" if has_range else args.mode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TradingTPlus production flows")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sync-master-data", help="Sync SSI master data into DB")
    sub.add_parser("init", help="Alias for sync-master-data")

    daily = sub.add_parser(
        "daily", help="Daily SSI ingest only; no features/signals/backtests"
    )
    daily.add_argument(
        "date",
        nargs="?",
        help="Trading date DD/MM/YYYY; defaults to latest previous weekday",
    )
    daily.add_argument("--symbols", nargs="+", default=None)

    intraday_ingest = sub.add_parser(
        "intraday-ingest",
        help="SSI IntradayOhlc 1m ingest only; no features/signals/backtests",
    )
    intraday_ingest.add_argument("date", nargs="?", help="Trading date DD/MM/YYYY")
    intraday_ingest.add_argument("--symbols", nargs="+", default=None)

    eod = sub.add_parser(
        "eod",
        help="Daily ingest + intraday ingest + completeness; no features",
    )
    eod.add_argument("date", nargs="?", help="Trading date DD/MM/YYYY")
    eod.add_argument("--symbols", nargs="+", default=None)

    for command, help_text in (
        ("backfill-daily", "Inclusive daily source-data backfill"),
        ("backfill-intraday", "Inclusive 1m intraday source-data backfill"),
        ("backfill", "Inclusive daily + intraday source-data backfill"),
    ):
        command_parser = sub.add_parser(command, help=help_text)
        command_parser.add_argument(
            "--from", "--from-date", dest="from_date", required=True
        )
        command_parser.add_argument(
            "--to", "--to-date", dest="to_date", required=True
        )
        command_parser.add_argument("--symbols", nargs="+", default=None)

    features = sub.add_parser(
        "features",
        help="Compatibility feature router; persists only 1d, 15m, and 60m",
    )
    features.add_argument(
        "--mode", choices=["incremental", "full"], default="incremental"
    )
    features.add_argument("--date", default=None)
    features.add_argument("--symbols", nargs="*", default=None)
    features.add_argument(
        "--timeframes",
        nargs="*",
        default=list(DEFAULT_PERSISTED_FEATURE_TIMEFRAMES),
        help="Persisted feature timeframes: 15m 60m 1d",
    )

    features_daily = sub.add_parser(
        "features-daily",
        help="stock_daily-only 1d feature pipeline with date/range/full scopes",
    )
    features_daily.add_argument(
        "--mode", choices=["incremental", "full"], default="incremental"
    )
    features_daily.add_argument("--date", default=None)
    _add_range_arguments(features_daily)
    features_daily.add_argument("--symbols", nargs="*", default=None)

    features_intraday = sub.add_parser(
        "features-intraday",
        help="Closed-candle 15m/60m features from clean 1m source",
    )
    features_intraday.add_argument(
        "--mode", choices=["incremental", "full"], default="incremental"
    )
    features_intraday.add_argument("--date", default=None)
    _add_range_arguments(features_intraday)
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
        help="One-date cutoff: HH:MM Vietnam time or timezone-aware timestamp",
    )

    intraday = sub.add_parser(
        "intraday",
        help="Legacy alias for incremental 15m/60m feature calculation",
    )
    intraday.add_argument("--snapshot-time", default=None)
    intraday.add_argument("--symbols", nargs="*", default=None)
    intraday.add_argument(
        "--timeframes", nargs="*", default=list(PERSISTED_INTRADAY_TIMEFRAMES)
    )

    streaming = sub.add_parser(
        "streaming-ingest",
        help="Bounded SSI streaming ingest; dry-run unless --write is passed",
    )
    streaming.add_argument("--symbols", nargs="*", default=[])
    streaming.add_argument("--indexes", nargs="*", default=[])
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
    )
    streaming.add_argument("--timeout", type=int, default=60)
    streaming.add_argument("--max-messages-per-channel", type=int, default=1)
    streaming.add_argument("--write", action="store_true", default=False)
    streaming.add_argument("--debug", action="store_true", default=False)
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
            summary = daily_run(
                args.date, symbols=normalize_symbol_scope(args.symbols)
            )
        elif args.command == "intraday-ingest":
            summary = run_intraday_ingest(
                args.date, symbols=normalize_symbol_scope(args.symbols)
            )
        elif args.command == "eod":
            summary = run_eod_pipeline(
                args.date, symbols=normalize_symbol_scope(args.symbols)
            )
        elif args.command in {"backfill-daily", "backfill-intraday", "backfill"}:
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
        elif args.command == "features":
            summary = run_feature_engine_with_summary(
                symbols=normalize_symbol_scope(args.symbols),
                mode=args.mode,
                timeframes=tuple(args.timeframes),
                target_date=args.date,
            )
        elif args.command == "features-daily":
            scope = _validate_feature_scope(args)
            symbols = normalize_symbol_scope(args.symbols)
            if scope == "range":
                summary = run_daily_feature_backfill(
                    args.from_date, args.to_date, symbols=symbols
                )
            else:
                summary = run_daily_features_with_summary(
                    symbols=symbols,
                    mode=args.mode,
                    target_date=args.date,
                )
        elif args.command == "features-intraday":
            scope = _validate_feature_scope(args)
            symbols = normalize_symbol_scope(args.symbols)
            if scope == "range":
                summary = run_intraday_feature_backfill(
                    args.from_date,
                    args.to_date,
                    symbols=symbols,
                    timeframes=tuple(args.timeframes),
                )
            else:
                summary = run_intraday_features_with_summary(
                    symbols=symbols,
                    mode=args.mode,
                    timeframes=tuple(args.timeframes),
                    target_date=args.date,
                    as_of=args.as_of,
                )
        elif args.command == "intraday":
            summary = run_intraday_pipeline(
                snapshot_time=args.snapshot_time,
                symbols=normalize_symbol_scope(args.symbols),
                timeframes=tuple(args.timeframes),
            )
        elif args.command == "streaming-ingest":
            summary = run_streaming_ingest(
                symbols=[symbol.upper() for symbol in args.symbols],
                indexes=[index.upper() for index in args.indexes],
                channels=list(args.channels),
                timeout_sec=args.timeout,
                max_messages_per_channel=args.max_messages_per_channel,
                write=args.write,
                debug=args.debug,
            )
        else:
            parser.error(f"Unsupported command: {args.command}")
            return 2

        _print_summary(summary)
        return _status_to_exit(summary)
    except ValueError as exc:
        print(f"❌ Invalid arguments: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"❌ {args.command} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
