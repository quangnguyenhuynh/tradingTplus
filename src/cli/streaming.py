from __future__ import annotations
from src.ingest import run_streaming_ingest
from .common import _print_summary, _status_to_exit, _source_kwargs

def run(args):
    if args.command == "streaming-ingest":
        summary = run_streaming_ingest(
            symbols=[symbol.upper() for symbol in args.symbols],
            indexes=[index.upper() for index in args.indexes],
            channels=list(args.channels),
            timeout_sec=args.timeout,
            max_messages_per_channel=args.max_messages_per_channel,
            write=args.write,
            debug=args.debug,
        )
        _print_summary(summary)
        return _status_to_exit(summary)
    raise ValueError(f"Unsupported command: {args.command}")
