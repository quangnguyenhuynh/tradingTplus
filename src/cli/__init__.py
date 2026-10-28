"""Production CLI dispatch with parsing and preflight before any service call."""
from __future__ import annotations
import sys
from importlib import import_module
from .parser import build_parser
from .common import _print_summary
from src.providers.ssi.capabilities import CapabilityUnavailableError
from src.providers.ssi.registry import resolve_source

COMMAND_GROUPS = {'analogs': 'analogs', 'init': 'maintenance', 'sync-master-data': 'maintenance', 'index-eod': 'index', 'index-eod-backfill': 'index', 'index-check': 'index', 'index-preview': 'index', 'index-features-preview': 'index', 'index-features-daily': 'index', 'index-features-backfill': 'index', 'index-features-check': 'index', 'stock-screener-config': 'screener', 'stock-screener': 'screener', 'foreign-features-preview': 'foreign', 'foreign-features-daily': 'foreign', 'foreign-features-backfill': 'foreign', 'foreign-features-check': 'foreign', 'foreign-rank': 'foreign', 'foreign-symbol': 'foreign', 'intraday-ingest': 'stock', 'stock-eod': 'stock', 'stock-intraday': 'stock', 'stock-eod-backfill': 'maintenance', 'backfill-intraday': 'maintenance', 'backfill': 'maintenance', 'refill': 'maintenance', 'features': 'features', 'features-daily': 'features', 'features-intraday': 'features', 'streaming-ingest': 'streaming'}
DISABLED = {
    "intraday-ingest": "stock_intraday",
    "backfill": "stock_intraday",
    "refill": "stock_intraday", "streaming-ingest": "streaming",
}
# Argparse retains the invoked alias. Keep existing handler keys, runners and
# JSON flow identities; only unrelated intraday aliases are normalized.
BACKFILL_COMMANDS = {
    "stock-intraday-backfill": "backfill-intraday",
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    args.command = BACKFILL_COMMANDS.get(args.command, args.command)
    try:
        requested = getattr(args, "data_source", None)
        if requested is not None and args.command not in {"init", "sync-master-data"}:
            intraday = args.command in {"stock-intraday", "backfill-intraday"}
            dataset = ("stock_intraday" if intraday else
                       "index_daily" if args.command.startswith("index-") else "stock_daily")
            # Only the guarded operator paths may resolve intraday preview.
            # This lookup never constructs an adapter or promotes readiness.
            resolve_source(dataset, requested, production=not intraday)
        if args.command in DISABLED:
            raise CapabilityUnavailableError(DISABLED[args.command])
        handler = import_module(f"src.cli.{COMMAND_GROUPS[args.command]}")
        return handler.run(args)
    except CapabilityUnavailableError as exc:
        _print_summary(exc.as_summary())
        return 1
    except ValueError as exc:
        print(f"Invalid arguments: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"{args.command} failed: {exc}", file=sys.stderr)
        return 1
