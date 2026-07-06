#!/usr/bin/env python
"""Verify required SSI ingest tables/columns are visible through Supabase PostgREST.

This script is read-only. It checks table existence and required columns by issuing
`select(...).limit(1)` calls. Unique index checks are printed as SQL snippets
because Supabase projects commonly do not expose `pg_indexes` via PostgREST.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.client import SupabaseClient

REQUIRED_COLUMNS = {
    "securities": ["symbol", "market", "stock_name", "stock_en_name", "sec_type", "exchange", "issuer", "lot_size", "raw", "updated_at"],
    "stock_daily": ["symbol", "trading_date", "price_change", "per_price_change", "ceiling_price", "floor_price", "ref_price", "open_price", "highest_price", "lowest_price", "close_price", "average_price", "close_price_adjusted", "total_match_vol", "total_match_val", "total_deal_vol", "total_deal_val", "total_traded_vol", "total_traded_value", "foreign_buy_vol_total", "foreign_sell_vol_total", "foreign_buy_val_total", "foreign_sell_val_total", "foreign_current_room", "net_foreign_vol", "net_foreign_val", "total_buy_trade", "total_buy_trade_vol", "total_sell_trade", "total_sell_trade_vol", "raw", "created_at", "updated_at"],
    "raw_daily": ["symbol", "trading_date", "data_hash", "payload", "created_at"],
    "indexes": ["index_code", "index_name", "exchange", "raw", "updated_at"],
    "index_components": ["index_code", "symbol", "exchange", "raw", "updated_at"],
    "index_daily": ["index_code", "trading_date", "index_value", "change", "ratio_change", "total_trade", "total_match_vol", "total_match_val", "total_deal_vol", "total_deal_val", "total_vol", "total_val", "type_index", "index_name", "advances", "no_changes", "declines", "ceilings", "floors", "trading_session", "market", "exchange", "raw"],
}

REQUIRED_UNIQUE_INDEXES = {
    "securities": "primary key (symbol)",
    "stock_daily": "unique index on (symbol, trading_date)",
    "raw_daily": "unique index on (symbol, trading_date, data_hash)",
    "indexes": "primary key (index_code)",
    "index_components": "unique index on (index_code, symbol)",
    "index_daily": "unique index on (index_code, trading_date)",
}


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser(description="Read-only SSI ingest schema verification.").parse_args()


def main() -> None:
    parse_args()
    db = SupabaseClient()
    passed = 0
    failed = 0

    print("🔎 Checking SSI ingest schema via Supabase read-only selects...")
    for table, columns in REQUIRED_COLUMNS.items():
        select_expr = ",".join(columns)
        try:
            db.client.table(table).select(select_expr).limit(1).execute()
            print(f"✅ PASS table/columns: {table} ({len(columns)} columns)")
            passed += 1
        except Exception as exc:
            print(f"❌ FAIL table/columns: {table}: {exc}")
            failed += 1

    print("\nℹ️ Required unique indexes/constraints to verify in Supabase SQL Editor:")
    for table, requirement in REQUIRED_UNIQUE_INDEXES.items():
        print(f"   - {table}: {requirement}")

    print("\nOptional SQL index verification:")
    print("""
select tablename, indexname, indexdef
from pg_indexes
where schemaname = 'public'
  and tablename in ('securities','stock_daily','raw_daily','indexes','index_components','index_daily')
order by tablename, indexname;
""".strip())

    print(f"\nSUMMARY: {passed} PASS, {failed} FAIL")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
