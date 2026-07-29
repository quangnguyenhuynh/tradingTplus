#!/usr/bin/env python3
"""Backfill persisted features for an inclusive date range."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.features import (  # noqa: E402
    PERSISTED_INTRADAY_TIMEFRAMES,
    run_daily_feature_backfill,
    run_intraday_feature_backfill,
)
from src.pipeline.symbol_scope import normalize_symbol_scope  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inclusive feature backfill; does not ingest source data",
    )
    sub = parser.add_subparsers(dest="flow", required=True)

    for flow in ("daily", "intraday"):
        command = sub.add_parser(flow)
        command.add_argument(
            "--from",
            "--from-date",
            dest="from_date",
            required=True,
            help="Inclusive start date DD/MM/YYYY",
        )
        command.add_argument(
            "--to",
            "--to-date",
            dest="to_date",
            required=True,
            help="Inclusive end date DD/MM/YYYY",
        )
        command.add_argument(
            "--symbols",
            nargs="+",
            default=None,
            help="Optional symbol scope; omitted means all master symbols",
        )

    intraday = sub.choices["intraday"]
    intraday.add_argument(
        "--timeframes",
        nargs="+",
        default=list(PERSISTED_INTRADAY_TIMEFRAMES),
        help="Persisted intraday feature timeframes: 15m 60m",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        symbols = normalize_symbol_scope(args.symbols)
        if args.flow == "daily":
            summary = run_daily_feature_backfill(
                args.from_date,
                args.to_date,
                symbols=symbols,
            )
        else:
            summary = run_intraday_feature_backfill(
                args.from_date,
                args.to_date,
                symbols=symbols,
                timeframes=tuple(args.timeframes),
            )
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
        return 1 if summary.get("status") == "FAILED" else 0
    except ValueError as exc:
        print(f"❌ Invalid arguments: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"❌ feature backfill failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
