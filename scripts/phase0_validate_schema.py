#!/usr/bin/env python3
"""Read-only Phase 0 PostgreSQL catalog verification."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.validation.phase0 import verify_schema


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Phase 0 production schema using read-only catalog queries.")
    parser.add_argument("--database-url", default=os.getenv("PHASE0_DATABASE_URL"), help="PostgreSQL URL; defaults to PHASE0_DATABASE_URL.")
    args = parser.parse_args()
    if not args.database_url:
        print(json.dumps({"status": "UNKNOWN", "reason": "PHASE0_DATABASE_URL is not configured", "read_only": True}, indent=2))
        raise SystemExit(2)
    import psycopg
    with psycopg.connect(args.database_url, options="-c default_transaction_read_only=on") as connection:
        result = verify_schema(connection)
    print(json.dumps(result, indent=2, default=str))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
