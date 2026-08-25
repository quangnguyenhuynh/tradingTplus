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
  python main.py refill --symbol SSI --from DD/MM/YYYY --to DD/MM/YYYY
  python main.py features-daily (--date DD/MM/YYYY | --from DD/MM/YYYY --to DD/MM/YYYY | --mode full)
  python main.py features-intraday (--date DD/MM/YYYY | --from DD/MM/YYYY --to DD/MM/YYYY | --mode full)
  python main.py features [--date DD/MM/YYYY] [--symbols SSI HPG] [--timeframes 15m 60m 1d]
  python main.py intraday [--symbols SSI HPG] [--timeframes 15m 60m]
  python main.py index-preview --date YYYY-MM-DD --indexes VNINDEX [--raw | --json]
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
from src.features.runtime import atomic_replace_features
from src.pipeline import (
    daily_run,
    init_symbols,
    run_backfill_pipeline,
    run_daily_backfill_pipeline,
    run_eod_pipeline,
    run_intraday_backfill_pipeline,
    run_intraday_ingest,
    run_intraday_pipeline,
    run_index_daily_ingest,
    run_index_backfill_pipeline,
    check_index_completeness,
    run_refill_pipeline,
    run_streaming_ingest,
)
from src.pipeline.symbol_scope import normalize_symbol_scope
from src.pipeline.index_scope import normalize_index_scope
from src.pipeline.index_daily_preview import render_index_daily_preview, run_index_daily_preview
from src.analogs.cli import run as run_analogs


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

    index_daily = sub.add_parser("index-daily", help="SSI DailyIndex raw + validated clean ingest only")
    index_daily.add_argument("date", nargs="?", help="Trading date YYYY-MM-DD or DD/MM/YYYY; defaults to latest previous weekday")
    index_daily.add_argument("--indexes", nargs="+", default=None, help="Index codes; omitted means all index_master rows")

    index_backfill = sub.add_parser("index-backfill", help="Inclusive DailyIndex source-data backfill")
    index_backfill.add_argument("--from", "--from-date", dest="from_date", required=True, help="Inclusive start date YYYY-MM-DD or DD/MM/YYYY")
    index_backfill.add_argument("--to", "--to-date", dest="to_date", required=True, help="Inclusive end date YYYY-MM-DD or DD/MM/YYYY")
    index_backfill.add_argument("--indexes", nargs="+", default=None)

    index_check = sub.add_parser("index-check", help="Read-only index raw/clean completeness check")
    index_check.add_argument("date", nargs="?", help="Trading date YYYY-MM-DD or DD/MM/YYYY; defaults to latest previous weekday")
    index_check.add_argument("--indexes", nargs="+", default=None)

    index_preview = sub.add_parser(
        "index-preview",
        help="Read-only SSI DailyIndex preview; never reads or writes database rows",
    )
    preview_dates = index_preview.add_mutually_exclusive_group(required=True)
    preview_dates.add_argument("--date", help="Trading date YYYY-MM-DD or DD/MM/YYYY")
    preview_dates.add_argument("--from", dest="from_date", help="Inclusive start date YYYY-MM-DD or DD/MM/YYYY")
    index_preview.add_argument("--to", dest="to_date", help="Inclusive end date (required with --from)")
    index_preview.add_argument(
        "--indexes",
        required=True,
        help="Comma-separated index codes, for example VNINDEX,HNXINDEX",
    )
    preview_output = index_preview.add_mutually_exclusive_group()
    preview_output.add_argument("--raw", action="store_true", help="Print SSI payload rows as JSON")
    preview_output.add_argument("--json", action="store_true", dest="as_json", help="Print normalized rows as JSON")
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
    eod.add_argument("--indexes", nargs="+", default=None, help="Index codes; omitted means all index_master rows")
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

    refill = sub.add_parser(
        "refill",
        help="Single-symbol source, completeness, and 1d/15m/60m feature refill",
    )
    refill.add_argument("--symbol", required=True, help="Exactly one stock symbol; ALL is forbidden")
    refill.add_argument(
        "--from", "--from-date", dest="from_date", required=True,
        help="Inclusive start date DD/MM/YYYY",
    )
    refill.add_argument(
        "--to", "--to-date", dest="to_date", required=True,
        help="Inclusive end date DD/MM/YYYY",
    )

    features = sub.add_parser(
        "features",
        help="Compatibility feature router; persists only 1d, 15m, and 60m",
    )
    features.add_argument(
        "--mode",
        choices=["incremental", "full"],
        default="incremental",
        help=(
            "incremental uses per-stream watermarks and bounded warm-up; "
            "full recomputes and upserts all selected history without deleting"
        ),
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
        choices=["incremental", "full", "replace", "rebuild-clean"],
        default="incremental",
        help=(
            "incremental uses a 5-year warm-up; full is non-destructive upsert; "
            "replace/rebuild-clean atomically replaces one exact scope"
        ),
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
        choices=["incremental", "full", "replace", "rebuild-clean"],
        default="incremental",
        help=(
            "incremental uses 250 observed sessions; full is non-destructive "
            "upsert; replace/rebuild-clean atomically replaces one exact scope"
        ),
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

    analogs = sub.add_parser(
        "analogs", help="Phase 1 same-symbol EOD Historical Analog analysis"
    )
    analog_sub = analogs.add_subparsers(dest="analog_command", required=True)
    profiles = analog_sub.add_parser("profiles", help="Profile registry operations")
    profile_sub = profiles.add_subparsers(dest="profile_command", required=True)
    profile_sub.add_parser("list", help="List registered profiles")
    register = profile_sub.add_parser(
        "register", aliases=["sync"], help="Register exact source-controlled profile"
    )
    register.add_argument("--profile", default="TPLUS_ANALOG_CORE_EOD")
    register.add_argument("--version", type=int, default=1)
    register.add_argument("--config-hash")
    register.add_argument(
        "--apply", action="store_true", help="Write; omitted is dry-run"
    )
    history = analog_sub.add_parser("history", help="Build snapshot/outcome history")
    history_sub = history.add_subparsers(dest="history_command", required=True)
    build = history_sub.add_parser("build")
    build.add_argument("--profile", required=True)
    build.add_argument("--version", type=int, required=True)
    build.add_argument("--config-hash", required=True)
    build.add_argument("--symbols", nargs="+", required=True)
    build.add_argument("--from", dest="from_date", required=True)
    build.add_argument("--to", dest="to_date", required=True)
    build.add_argument(
        "--mode", choices=["full", "incremental", "replace"], required=True
    )
    build.add_argument("--apply", action="store_true")
    build.add_argument("--confirm-replace", action="store_true")
    validate = analog_sub.add_parser(
        "validate", help="Chronological calibration/validation/final evidence"
    )
    validate.add_argument("--profile", required=True)
    validate.add_argument("--version", type=int, required=True)
    validate.add_argument("--symbols", nargs="+", required=True)
    validate.add_argument("--from", dest="from_date", required=True)
    validate.add_argument("--to", dest="to_date", required=True)
    validate.add_argument(
        "--run-type", choices=["calibration", "validation", "final"], required=True
    )
    validate.add_argument("--thresholds", nargs="*", type=float)
    validate.add_argument("--final-test-start")
    validate.add_argument("--apply", action="store_true")
    for decision in ("approve", "reject"):
        review = analog_sub.add_parser(
            decision, help=f"Audit a manual {decision} decision"
        )
        review.add_argument("--profile", required=True)
        review.add_argument("--version", type=int, required=True)
        review.add_argument("--validation-run", required=True)
        review.add_argument("--reviewer", required=True)
        review.add_argument("--reason", required=True)
        review.add_argument("--apply", action="store_true")
    query = analog_sub.add_parser(
        "query", help="Persist an approved production analysis"
    )
    query.add_argument("--profile", required=True)
    query.add_argument("--version", type=int, required=True)
    query.add_argument("--symbol", required=True)
    query.add_argument("--date", required=True)
    query.add_argument("--checkpoint", default="EOD", choices=["EOD"])
    query.add_argument("--apply", action="store_true")
    inspect = analog_sub.add_parser(
        "inspect", help="Read source data and calculate research evidence without writes"
    )
    inspect.add_argument("--profile", required=True)
    inspect.add_argument("--version", type=int, required=True)
    inspect.add_argument("--symbol", required=True)
    inspect.add_argument("--date", required=True)
    inspect.add_argument("--checkpoint", default="EOD", choices=["EOD"])
    inspect.add_argument("--distance-threshold", type=float, required=True)
    daily_analog = analog_sub.add_parser(
        "daily", help="Separate idempotent EOD Analog runner"
    )
    daily_sub = daily_analog.add_subparsers(dest="daily_command", required=True)
    daily_run = daily_sub.add_parser("run")
    daily_run.add_argument("--profile", required=True)
    daily_run.add_argument("--version", type=int, required=True)
    daily_run.add_argument("--symbols", nargs="+", required=True)
    daily_run.add_argument("--date", required=True)
    daily_run.add_argument("--apply", action="store_true")
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
    if args.mode in {"replace", "rebuild-clean"}:
        if args.date is not None or not has_range:
            raise ValueError(
                "replace/rebuild-clean requires --from and --to, not --date"
            )
        return "replace"
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
        if args.command == "analogs":
            summary = run_analogs(args)
            _print_summary(summary)
            return 0 if summary.get("status") not in {"FAILED"} else 1
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
        if args.command == "index-daily":
            summary = run_index_daily_ingest(args.date, indexes=normalize_index_scope(args.indexes))
            _print_summary(summary); return _status_to_exit(summary)
        if args.command == "index-backfill":
            summary = run_index_backfill_pipeline(args.from_date, args.to_date, indexes=normalize_index_scope(args.indexes))
            _print_summary(summary); return _status_to_exit(summary)
        if args.command == "index-check":
            summary = check_index_completeness(args.date, indexes=normalize_index_scope(args.indexes))
            _print_summary(summary); return _status_to_exit(summary)
        if args.command == "index-preview":
            if bool(args.from_date) != bool(args.to_date):
                raise ValueError("--from and --to must be provided together")
            indexes = normalize_index_scope(args.indexes.split(","))
            preview = run_index_daily_preview(
                indexes=indexes or [], single_date=args.date,
                from_date=args.from_date, to_date=args.to_date,
            )
            print(render_index_daily_preview(preview, raw=args.raw, as_json=args.as_json))
            return 0
        if args.command == "intraday-ingest":
            summary = run_intraday_ingest(
                args.date,
                symbols=normalize_symbol_scope(args.symbols),
            )
            _print_summary(summary)
            return _status_to_exit(summary)
        if args.command == "eod":
            kwargs = {"symbols": normalize_symbol_scope(args.symbols)}
            if args.indexes is not None:
                kwargs["indexes"] = normalize_index_scope(args.indexes)
            summary = run_eod_pipeline(args.date, **kwargs)
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
        if args.command == "refill":
            symbol = normalize_symbol_scope([args.symbol])[0]
            summary = run_refill_pipeline(args.from_date, args.to_date, symbol)
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
            if scope == "replace":
                summary = atomic_replace_features(
                    symbols=symbols,
                    timeframes=("1d",),
                    start=args.from_date,
                    end=args.to_date,
                )
            elif scope == "range":
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
            if scope == "replace":
                summary = atomic_replace_features(
                    symbols=symbols,
                    timeframes=timeframes,
                    start=args.from_date,
                    end=args.to_date,
                )
            elif scope == "range":
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
