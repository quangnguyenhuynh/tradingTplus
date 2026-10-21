from __future__ import annotations
from src.ingest.shared.symbol_scope import normalize_symbol_scope
from src.research.screener import run_stock_screener
from src.research.screener.config import describe_config
from .common import _print_summary, _status_to_exit, _source_kwargs

def run(args):
    if args.command == "stock-screener-config":
        summary = describe_config(args.version, args.language, apply=args.apply)
        _print_summary(summary)
        return _status_to_exit(summary)
    if args.command == "stock-screener":
        summary = run_stock_screener(
            args.date, normalize_symbol_scope(args.symbols), apply=args.apply,
            **({"version": args.version} if args.version != "v1" else {}),
        )
        _print_summary(summary)
        return _status_to_exit(summary)
    raise ValueError(f"Unsupported command: {args.command}")
