from __future__ import annotations
from src.ingest import init_symbols, run_backfill_pipeline, run_daily_backfill_pipeline, run_intraday_backfill_pipeline, run_refill_pipeline
from src.ingest.shared.symbol_scope import normalize_symbol_scope
from .common import _print_summary, _status_to_exit, _source_kwargs

def run(args):
    if args.command in {"init", "sync-master-data"}:
        summary = init_symbols(dataset=args.dataset, data_source=args.data_source, write=args.write)
        _print_summary(summary)
        return 0 if summary.get("status") == "OK" else 1
    if args.command == "backfill-intraday":
        summary = run_intraday_backfill_pipeline(args.from_date, args.to_date, symbols=args.symbols,
                                                 write=args.write, **_source_kwargs(args))
        _print_summary(summary)
        return 0 if summary.get("status") == "OK" else 1
    if args.command in {"stock-eod-backfill", "backfill"}:
        runner = {
            "stock-eod-backfill": run_daily_backfill_pipeline,
            "backfill": run_backfill_pipeline,
        }[args.command]
        summary = runner(
            args.from_date,
            args.to_date,
            symbols=normalize_symbol_scope(args.symbols),
            **_source_kwargs(args),
        )
        _print_summary(summary)
        return _status_to_exit(summary)
    if args.command == "refill":
        symbol = normalize_symbol_scope([args.symbol])[0]
        summary = run_refill_pipeline(args.from_date, args.to_date, symbol, **_source_kwargs(args))
        _print_summary(summary)
        return _status_to_exit(summary)
    raise ValueError(f"Unsupported command: {args.command}")
