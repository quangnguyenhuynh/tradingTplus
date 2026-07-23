#!/usr/bin/env python
"""Deprecated wrapper for the production full-market EOD-style backfill.

Prefer:
    python main.py backfill --from DD/MM/YYYY --to DD/MM/YYYY
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.backfill import run_backfill_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deprecated wrapper for the production EOD-style backfill. Writes to Supabase."
    )
    parser.add_argument("--from", "--from-date", dest="from_date", required=True, help="Inclusive start date DD/MM/YYYY")
    parser.add_argument("--to", "--to-date", dest="to_date", required=True, help="Inclusive end date DD/MM/YYYY")
    args = parser.parse_args()

    print("⚠️ scripts/backfill_sample.py is deprecated; prefer `python main.py backfill ...`.")
    summary = run_backfill_pipeline(args.from_date, args.to_date)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 1 if summary.get("status") == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
