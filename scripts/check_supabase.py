#!/usr/bin/env python3
"""Read-only Supabase connectivity and core-table smoke check."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import config
from src.database.client import SupabaseClient

CORE_TABLE_COLUMNS = {
    "securities": "symbol",
    "raw_daily": "symbol",
    "stock_daily": "symbol",
    "raw_intraday": "symbol",
    "stock_intraday": "symbol",
    "indexes": "index_code",
    "index_daily": "index_code",
    "foreign_trading": "symbol",
    "orderbook_snapshot": "symbol",
    "features": "symbol",
}


def main() -> int:
    missing_env = [
        name
        for name, value in {
            "SUPABASE_URL": config.SUPABASE_URL,
            "SUPABASE_SERVICE_KEY": config.SUPABASE_SERVICE_KEY,
        }.items()
        if not value
    ]
    if missing_env:
        print(f"❌ Missing required environment variables: {', '.join(missing_env)}")
        return 2

    try:
        db = SupabaseClient()
    except Exception as exc:
        print(f"❌ Supabase connection failed: {exc}")
        return 1

    failed: list[str] = []
    print("🔎 Checking Supabase connection and core tables (read-only)...")
    for table, column in CORE_TABLE_COLUMNS.items():
        try:
            db.get().table(table).select(column).limit(1).execute()
            print(f"✅ {table}")
        except Exception as exc:
            failed.append(table)
            print(f"❌ {table}: {exc}")

    if failed:
        print(f"\nSUMMARY: {len(CORE_TABLE_COLUMNS) - len(failed)} PASS, {len(failed)} FAIL")
        return 1

    print(f"\nSUMMARY: {len(CORE_TABLE_COLUMNS)} PASS, 0 FAIL")
    print("✅ Read-only Supabase smoke check completed; no rows were written or deleted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
