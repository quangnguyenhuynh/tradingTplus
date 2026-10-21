from __future__ import annotations
from src.research.analogs.cli import run as run_analogs
from .common import _print_summary, _status_to_exit, _source_kwargs

def run(args):
    if args.command == "analogs":
        summary = run_analogs(args)
        _print_summary(summary)
        return 0 if summary.get("status") not in {"FAILED"} else 1
    raise ValueError(f"Unsupported command: {args.command}")
