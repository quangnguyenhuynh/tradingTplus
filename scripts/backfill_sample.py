#!/usr/bin/env python
"""Deprecated CLI delegate for the production EOD-based backfill pipeline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.backfill import run_backfill_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deprecated: use `python main.py backfill` instead. Writes through EOD.")
    parser.add_argument("--from", "--from-date", dest="from_date", required=True, help="Inclusive start date DD/MM/YYYY")
    parser.add_argument("--to", "--to-date", dest="to_date", required=True, help="Inclusive end date DD/MM/YYYY")
    args = parser.parse_args(argv)
    print("⚠️ Deprecated: use `python main.py backfill --from ... --to ...`.", file=sys.stderr)
    try:
        summary = run_backfill_pipeline(args.from_date, args.to_date)
    except ValueError as exc:
        print(f"❌ Invalid arguments: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"❌ Backfill failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 1 if summary.get("status") == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
