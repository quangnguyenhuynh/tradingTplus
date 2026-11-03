from __future__ import annotations
from src.ingest import daily_run, run_stock_eod_pipeline, run_stock_intraday_pipeline, run_intraday_ingest
from src.ingest.shared.symbol_scope import normalize_symbol_scope
from .common import _print_summary, _status_to_exit, _source_kwargs

def run(args):
    if args.command == 'stock-eod-quality':
        if args.date and args.to_date or args.from_date and not args.to_date:
            raise ValueError('Use --date alone or --from/--to together')
        from src.quality.stock_daily_diagnostics import inspect_daily
        try:
            report=inspect_daily(args.symbols, args.date or args.from_date, args.to_date,
                                 missing_only=args.raw_clean_missing)
        except ValueError:
            raise
        except Exception:
            _print_summary({'flow':'stock-eod-quality','mode':'READ_ONLY','status':'FAILED',
                            'error_type':'DIAGNOSTIC_DB_READ_FAILED'})
            return 1
        _print_summary(report)
        return 0
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
