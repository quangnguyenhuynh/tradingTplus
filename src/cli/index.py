from __future__ import annotations
from src.ingest import run_index_daily_ingest, run_index_backfill_pipeline, check_index_completeness
from src.ingest.shared.index_scope import normalize_index_scope
from src.ingest.index_daily.index_daily_preview import render_index_daily_preview, run_index_daily_preview
from src.features.index import check_index_features, run_index_features_backfill, run_index_features_daily, run_index_features_preview
from .common import _print_summary, _status_to_exit, _source_kwargs

def run(args):
    if args.command == "index-daily":
        summary = run_index_daily_ingest(args.date, indexes=normalize_index_scope(args.indexes), **_source_kwargs(args))
        _print_summary(summary); return _status_to_exit(summary)
    if args.command == "index-backfill":
        summary = run_index_backfill_pipeline(args.from_date, args.to_date, indexes=normalize_index_scope(args.indexes), **_source_kwargs(args))
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
    if args.command == "index-features-preview":
        summary = run_index_features_preview(args.date, normalize_index_scope(args.indexes))
        _print_summary(summary)
        return _status_to_exit(summary)
    if args.command == "index-features-daily":
        summary = run_index_features_daily(args.date, normalize_index_scope(args.indexes))
        _print_summary(summary)
        return _status_to_exit(summary)
    if args.command == "index-features-backfill":
        summary = run_index_features_backfill(args.from_date, args.to_date, normalize_index_scope(args.indexes))
        _print_summary(summary)
        return _status_to_exit(summary)
    if args.command == "index-features-check":
        summary = check_index_features(args.from_date, args.to_date, normalize_index_scope(args.indexes))
        _print_summary(summary)
        return _status_to_exit(summary)
    raise ValueError(f"Unsupported command: {args.command}")
