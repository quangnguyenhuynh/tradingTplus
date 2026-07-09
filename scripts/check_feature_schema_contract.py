#!/usr/bin/env python3
"""Validate the Supabase features table against the phase 1 schema contract."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.database.client import SupabaseClient  # noqa: E402
from src.engine.feature_engine import FEATURE_COLUMNS  # noqa: E402

REQUIRED_COLUMNS = ["symbol", "timeframe", "time", "last_updated_at", *FEATURE_COLUMNS]
UNIQUE_CONFLICT_COLUMNS = ["symbol", "timeframe", "time"]


def _rpc(db: SupabaseClient, sql: str):
    return db._with_retry(lambda: db.get().rpc("execute_sql", {"query": sql}).execute(), action_name="feature schema contract SQL")


def main() -> int:
    db = SupabaseClient()

    columns_sql = """
    select column_name
    from information_schema.columns
    where table_schema = 'public' and table_name = 'features'
    order by ordinal_position;
    """
    constraints_sql = """
    select array_agg(a.attname order by x.ord) as columns
    from pg_index i
    join pg_class t on t.oid = i.indrelid
    join pg_namespace n on n.oid = t.relnamespace
    join lateral unnest(i.indkey) with ordinality as x(attnum, ord) on true
    join pg_attribute a on a.attrelid = t.oid and a.attnum = x.attnum
    where n.nspname = 'public'
      and t.relname = 'features'
      and i.indisunique
    group by i.indexrelid;
    """

    try:
        column_rows = _rpc(db, columns_sql).data or []
        unique_rows = _rpc(db, constraints_sql).data or []
    except Exception as exc:
        print(f"❌ Could not inspect Supabase schema via execute_sql RPC: {exc}")
        return 2

    actual_columns = {row["column_name"] for row in column_rows}
    missing = [column for column in REQUIRED_COLUMNS if column not in actual_columns]
    if missing:
        print("❌ features table is missing required phase 1 columns:")
        for column in missing:
            print(f"  - {column}")
    else:
        print("✅ features table contains all required phase 1 columns")

    has_unique = any(row.get("columns") == UNIQUE_CONFLICT_COLUMNS for row in unique_rows)
    if not has_unique:
        print("❌ features table is missing a unique index/constraint on (symbol, timeframe, time)")
    else:
        print("✅ features table supports on_conflict='symbol,timeframe,time'")

    if missing or not has_unique:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
