from __future__ import annotations
from src.ingest import daily_run, run_stock_eod_pipeline, run_stock_intraday_pipeline, run_intraday_ingest
from src.ingest.shared.symbol_scope import normalize_symbol_scope
from .common import _print_summary, _status_to_exit, _source_kwargs

def run(args):
    if args.command == "daily":
        summary = daily_run(
            args.date,
            symbols=normalize_symbol_scope(args.symbols),
            **_source_kwargs(args),
        )
        _print_summary(summary)
        return _status_to_exit(summary)
    if args.command == "intraday-ingest":
        summary = run_intraday_ingest(
            args.date,
            symbols=normalize_symbol_scope(args.symbols),
            **_source_kwargs(args),
        )
        _print_summary(summary)
        return _status_to_exit(summary)
    if args.command in {"stock-eod", "stock-daily"}:
        summary = run_stock_eod_pipeline(args.date, symbols=normalize_symbol_scope(args.symbols), **_source_kwargs(args))
        _print_summary(summary)
        return _status_to_exit(summary)
    if args.command == "stock-intraday":
        summary = run_stock_intraday_pipeline(args.date, symbols=normalize_symbol_scope(args.symbols), **_source_kwargs(args))
        _print_summary(summary)
        return _status_to_exit(summary)
    raise ValueError(f"Unsupported command: {args.command}")
