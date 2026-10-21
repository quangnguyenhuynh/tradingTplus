from __future__ import annotations
from src.ingest.shared.symbol_scope import normalize_symbol_scope
from src.features.foreign import check as check_foreign_features, preview as preview_foreign_features, run_backfill as run_foreign_features_backfill, run_daily as run_foreign_features_daily, run_history_rpc, run_ranking_rpc
from .common import _print_summary, _status_to_exit, _source_kwargs

def run(args):
    if args.command == "foreign-features-preview":
        summary = preview_foreign_features(args.date, args.symbol, args.calendar_file, show_source=args.show_source)
        _print_summary(summary); return _status_to_exit(summary)
    if args.command == "foreign-features-daily":
        summary = run_foreign_features_daily(args.date, normalize_symbol_scope(args.symbols), args.calendar_file, args.mode, dry_run=args.dry_run)
        _print_summary(summary); return _status_to_exit(summary)
    if args.command == "foreign-features-backfill":
        summary = run_foreign_features_backfill(args.from_date, args.to_date, normalize_symbol_scope(args.symbols), args.calendar_file, dry_run=args.dry_run)
        _print_summary(summary); return _status_to_exit(summary)
    if args.command == "foreign-features-check":
        summary = check_foreign_features(args.from_date, args.to_date, normalize_symbol_scope(args.symbols), args.calendar_file)
        _print_summary(summary); return _status_to_exit(summary)
    if args.command == "foreign-rank":
        _print_summary(run_ranking_rpc(args.date, args.ranking, args.window, args.sort, args.market, args.symbols, args.top, args.offset)); return 0
    if args.command == "foreign-symbol":
        _print_summary(run_history_rpc(args.symbol, args.date, args.lookback)); return 0
    raise ValueError(f"Unsupported command: {args.command}")
