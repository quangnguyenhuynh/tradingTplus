from __future__ import annotations
import argparse
from src.features import run_daily_feature_backfill, run_daily_features_with_summary, run_feature_engine_with_summary, run_intraday_feature_backfill, run_intraday_features_with_summary
from src.features.stock.runtime import atomic_replace_features
from src.ingest.shared.symbol_scope import normalize_symbol_scope
from .common import _print_summary, _status_to_exit, _source_kwargs

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

def run(args):
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
    raise ValueError(f"Unsupported command: {args.command}")
