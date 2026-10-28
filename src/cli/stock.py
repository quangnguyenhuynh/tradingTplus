from __future__ import annotations
from src.ingest import daily_run, run_stock_eod_pipeline, run_stock_intraday_pipeline, run_intraday_ingest
from src.ingest.shared.symbol_scope import normalize_symbol_scope
from .common import _print_summary, _status_to_exit, _source_kwargs

def run(args):
    if args.command == "intraday-ingest":
        summary = run_intraday_ingest(
            args.date,
            symbols=normalize_symbol_scope(args.symbols),
            **_source_kwargs(args),
        )
        _print_summary(summary)
        return _status_to_exit(summary)
    if args.command in {"stock-eod"}:
        summary = run_stock_eod_pipeline(args.date, symbols=normalize_symbol_scope(args.symbols), **_source_kwargs(args))
        _print_summary(summary)
        return _status_to_exit(summary)
    if args.command == "stock-intraday":
        summary = run_stock_intraday_pipeline(args.date, symbols=args.symbols, write=args.write, **_source_kwargs(args))
        _print_summary(summary)
        return 0 if summary.get("status") == "OK" else 1
    raise ValueError(f"Unsupported command: {args.command}")
