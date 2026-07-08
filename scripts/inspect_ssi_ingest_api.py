#!/usr/bin/env python
"""Inspect SSI API payloads and mapped ingest records in the CLI without DB writes.

This script is intentionally read-only. It fetches each SSI source used by the
ingest layer, maps representative records into the DB payload shape, and prints
counts/samples so operators can verify whether fetched data satisfies ingest
requirements before running daily/backfill jobs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.date_utils import latest_previous_weekday, parse_ddmmyyyy
from src.pipeline.fetch_one_day import build_intraday_records, build_raw_daily_record, build_stock_daily_record
from src.pipeline.foreign_trading import build_foreign_trading_record
from src.pipeline.index_data import build_index_daily_record, map_index_record
from src.pipeline.init_symbols import map_security_record
from src.pipeline.orderbook_snapshot import build_orderbook_record
from src.ssi.api import SSIApi


def _print_section(title: str) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def _print_json(title: str, value: Any, *, full_json: bool = False, max_chars: int = 5000) -> None:
    print(f"\n--- {title} ---")
    text = json.dumps(value, indent=2, ensure_ascii=False, default=str)
    if not full_json and len(text) > max_chars:
        print(text[:max_chars])
        print(f"... <truncated {len(text) - max_chars} chars; pass --full-json to print all>")
    else:
        print(text)


def _sample(rows: list[Any], limit: int) -> list[Any]:
    return rows[: max(limit, 0)]


def _resolve_date(value: str | None) -> str:
    if value:
        parsed = parse_ddmmyyyy(value)
        print(f"📅 Using explicit date: {parsed.ddmmyyyy} ({parsed.iso})")
        return parsed.ddmmyyyy
    fallback = latest_previous_weekday().strftime("%d/%m/%Y")
    parsed = parse_ddmmyyyy(fallback)
    print(f"📅 No --date supplied; using latest previous weekday for read-only inspection: {parsed.ddmmyyyy} ({parsed.iso})")
    return parsed.ddmmyyyy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only SSI API ingest inspector; prints raw and mapped samples.")
    parser.add_argument("--symbol", default="SSI", help="Stock symbol to inspect, e.g. SSI/FPT")
    parser.add_argument("--date", default=None, help="DD/MM/YYYY. Default: latest previous weekday (read-only).")
    parser.add_argument("--market", default="HOSE", help="Market for symbol/security list checks, default HOSE")
    parser.add_argument("--index-code", default="VNINDEX", help="Index code for DailyIndex/IndexComponents checks")
    parser.add_argument("--limit", type=int, default=3, help="Number of raw list rows to print per section")
    parser.add_argument("--full-json", action="store_true", help="Print full JSON payloads instead of truncating long sections")
    parser.add_argument("--skip-orderbook", action="store_true", help="Skip optional orderbook check")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbol = args.symbol.upper()
    date = _resolve_date(args.date)

    print("🔎 SSI INGEST API INSPECTOR (READ-ONLY)")
    print(f"   symbol     : {symbol}")
    print(f"   date       : {date}")
    print(f"   market     : {args.market}")
    print(f"   index_code : {args.index_code}")
    print("   db writes   : disabled")

    ssi = SSIApi()

    _print_section("1) Securities list / symbols")
    symbols = ssi.get_symbols()
    print(f"fetched symbols count: {len(symbols)}")
    _print_json("symbols sample raw", _sample(symbols, args.limit), full_json=args.full_json)

    _print_section("2) SecuritiesDetails -> securities mapping")
    security_details = ssi.get_security_details(symbol=symbol)
    if not security_details and args.market:
        print(f"⚠️ SecuritiesDetails by symbol returned 0 rows; retrying market={args.market}")
        security_details = [row for row in ssi.get_security_details(market=args.market) if str(row.get("Symbol") or row.get("symbol") or "").upper() == symbol]
    security_records = [record for record in (map_security_record(row) for row in security_details) if record]
    print(f"fetched security detail count: {len(security_details)}")
    print(f"mapped securities count: {len(security_records)}")
    _print_json("security details raw sample", _sample(security_details, args.limit), full_json=args.full_json)
    _print_json("securities mapped sample", _sample(security_records, args.limit), full_json=args.full_json)

    _print_section("3) DailyStockPrice -> raw_daily + stock_daily mapping")
    daily = ssi.get_daily_price(symbol, date)
    raw_daily_record = build_raw_daily_record(symbol, date, daily or {}) if daily else None
    stock_daily_record = build_stock_daily_record(symbol, date, daily or {}) if daily else None
    print(f"daily raw exists: {bool(daily)}")
    print(f"raw_daily mapped: {bool(raw_daily_record)}")
    print(f"stock_daily mapped: {bool(stock_daily_record)}")
    if not daily:
        print("⚠️ No DailyStockPrice data. This may be weekend/holiday/no trading data; intraday should not be inserted for this date.")
    _print_json("DailyStockPrice raw", daily, full_json=args.full_json)
    _print_json("raw_daily mapped", raw_daily_record, full_json=args.full_json)
    _print_json("stock_daily mapped", stock_daily_record, full_json=args.full_json)

    _print_section("4) IntradayOhlc 1m -> raw_intraday + stock_intraday mapping")
    intraday = ssi.get_intraday(symbol, date) if daily else []
    raw_intraday, clean_intraday = build_intraday_records(symbol, date, daily or {}, intraday) if daily else ([], [])
    print(f"fetched intraday candle count: {len(intraday)}")
    print(f"mapped raw_intraday count: {len(raw_intraday)}")
    print(f"mapped stock_intraday count: {len(clean_intraday)}")
    if clean_intraday:
        timeframes = sorted({row.get("timeframe") for row in clean_intraday})
        print(f"mapped stock_intraday timeframes: {timeframes}")
    _print_json("intraday raw sample", _sample(intraday, args.limit), full_json=args.full_json)
    _print_json("stock_intraday mapped sample", _sample(clean_intraday, args.limit), full_json=args.full_json)

    _print_section("5) Foreign trading derived from DailyStockPrice -> foreign_trading mapping")
    foreign_rows = ssi.get_foreign_trading(symbol=symbol, date=date)
    foreign_records = [record for record in (build_foreign_trading_record(symbol, date, row) for row in foreign_rows) if record]
    print(f"fetched foreign source row count: {len(foreign_rows)}")
    print(f"mapped foreign_trading count: {len(foreign_records)}")
    _print_json("foreign source raw sample", _sample(foreign_rows, args.limit), full_json=args.full_json)
    _print_json("foreign_trading mapped sample", _sample(foreign_records, args.limit), full_json=args.full_json)

    _print_section("6) IndexList -> indexes mapping")
    index_rows = ssi.get_index_list()
    if not index_rows:
        print("⚠️ IndexList without exchange returned 0 rows; retrying HOSE/HNX/UPCOM")
        for exchange in ("HOSE", "HNX", "UPCOM"):
            index_rows.extend(ssi.get_index_list(exchange=exchange))
    index_records = [record for record in (map_index_record(row) for row in index_rows) if record]
    print(f"fetched index list count: {len(index_rows)}")
    print(f"mapped indexes count: {len(index_records)}")
    _print_json("index list raw sample", _sample(index_rows, args.limit), full_json=args.full_json)
    _print_json("indexes mapped sample", _sample(index_records, args.limit), full_json=args.full_json)

    _print_section("7) DailyIndex -> index_daily mapping")
    daily_index_raw = ssi.get_daily_index_raw(args.index_code, date)
    daily_index_items = ssi._extract_items(daily_index_raw or {})
    daily_index_record = build_index_daily_record(args.index_code, date, daily_index_items[0]) if daily_index_items else None
    print(f"daily index raw item count: {len(daily_index_items)}")
    print(f"index_daily mapped: {bool(daily_index_record)}")
    if not daily_index_items:
        print("⚠️ No DailyIndex data for this date/code. Verify index code accepted by SSI API or date has market data.")
    _print_json("DailyIndex raw response", daily_index_raw, full_json=args.full_json)
    _print_json("index_daily mapped", daily_index_record, full_json=args.full_json)

    _print_section("8) IndexComponents")
    components = ssi.get_index_components(args.index_code)
    print(f"fetched index component count: {len(components)}")
    _print_json("index components raw sample", _sample(components, args.limit), full_json=args.full_json)

    if not args.skip_orderbook:
        _print_section("9) Optional orderbook snapshot")
        orderbook_raw = ssi.get_orderbook_snapshot(symbol)
        orderbook_record = build_orderbook_record(symbol, orderbook_raw)
        print(f"orderbook raw exists: {bool(orderbook_raw)}")
        print(f"orderbook_snapshot mapped: {bool(orderbook_record)}")
        if not orderbook_raw:
            print("⚠️ Orderbook REST endpoint is unsupported/missing unless SSI_ORDERBOOK_URL is configured for your account.")
        _print_json("orderbook raw", orderbook_raw, full_json=args.full_json)
        _print_json("orderbook_snapshot mapped", orderbook_record, full_json=args.full_json)

    print("\n✅ Read-only SSI ingest API inspection completed. No DB writes were attempted.")


if __name__ == "__main__":
    main()
