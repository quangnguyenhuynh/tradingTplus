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
    "foreign_trading": ["symbol", "trading_date", "foreign_buy_vol", "foreign_sell_vol", "foreign_buy_val", "foreign_sell_val", "net_foreign_vol", "net_foreign_val", "foreign_current_room", "raw"],
    "orderbook_snapshot": ["symbol", "time", "bid_price_1", "bid_vol_1", "ask_price_1", "ask_vol_1", "bid_price_10", "bid_vol_10", "ask_price_10", "ask_vol_10", "total_bid_depth_10", "total_ask_depth_10", "orderbook_imbalance", "pressure_score", "raw"],
    "stream_raw_snapshot": ["channel", "requested_channel", "rtype", "symbol", "index_code", "time", "source_time", "received_at", "trading_date", "payload", "payload_hash", "validation_status", "validation_issues"],
    "stream_quote_snapshot": ["symbol", "time", "trading_date", "total_bid_depth_10", "total_ask_depth_10", "orderbook_imbalance", "pressure_score", "raw"],
    "stream_trade_snapshot": ["symbol", "time", "trading_date", "raw"],
    "stream_foreign_snapshot": ["symbol", "time", "trading_date", "foreign_buy_vol", "foreign_sell_vol", "net_foreign_vol", "raw"],
    "stream_index_snapshot": ["index_code", "time", "trading_date", "index_value", "raw"],
    "stream_status_snapshot": ["symbol", "time", "trading_date", "trading_session", "trading_status", "raw"],
    "stream_bar_snapshot": ["symbol", "time", "trading_date", "open", "high", "low", "close", "volume", "value", "raw"],
}

REQUIRED_UNIQUE_INDEXES = {
    "securities": "primary key (symbol)",
    "stock_daily": "unique index on (symbol, trading_date)",
    "raw_daily": "unique index on (symbol, trading_date, data_hash)",
    "indexes": "primary key (index_code)",
    "index_components": "unique index on (index_code, symbol)",
    "index_daily": "unique index on (index_code, trading_date)",
    "foreign_trading": "unique index on (symbol, trading_date)",
    "orderbook_snapshot": "unique index on (symbol, time)",
    "stream_raw_snapshot": "unique index on (payload_hash)",
    "stream_quote_snapshot": "unique index on (symbol, time)",
    "stream_trade_snapshot": "unique index on (symbol, time)",
    "stream_foreign_snapshot": "unique index on (symbol, time)",
    "stream_index_snapshot": "unique index on (index_code, time)",
    "stream_status_snapshot": "unique index on (symbol, time)",
    "stream_bar_snapshot": "unique index on (symbol, time)",
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
  and tablename in ('securities','stock_daily','raw_daily','indexes','index_components','index_daily','foreign_trading','orderbook_snapshot','stream_raw_snapshot','stream_quote_snapshot','stream_trade_snapshot','stream_foreign_snapshot','stream_index_snapshot','stream_status_snapshot','stream_bar_snapshot')
order by tablename, indexname;
""".strip())

    print(f"\nSUMMARY: {passed} PASS, {failed} FAIL")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
