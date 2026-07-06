#!/usr/bin/env python
import argparse
import json
from src.database.client import SupabaseClient
from src.pipeline.fetch_one_day import build_raw_daily_record, build_stock_daily_record
from src.pipeline.index_data import build_index_daily_record
from src.ssi.api import SSIApi


def main():
    parser = argparse.ArgumentParser(description="Smoke-check complete SSI ingest mapping without DB writes by default.")
    parser.add_argument("--symbol", default="SSI")
    parser.add_argument("--date", default="05/07/2024", help="DD/MM/YYYY")
    parser.add_argument("--index-code", default="VNINDEX")
    parser.add_argument("--write", action="store_true", help="Persist fetched records to Supabase")
    args = parser.parse_args()

    ssi = SSIApi()
    daily = ssi.get_daily_price(args.symbol, args.date)
    daily_record = build_stock_daily_record(args.symbol, args.date, daily or {}) if daily else None
    raw_daily = build_raw_daily_record(args.symbol, args.date, daily or {}) if daily else None
    intraday = ssi.get_intraday(args.symbol, args.date)
    details = ssi.get_security_details(symbol=args.symbol)
    indexes = ssi.get_index_list()
    daily_index = ssi.get_daily_index(args.index_code, args.date)
    index_record = build_index_daily_record(args.index_code, args.date, daily_index or {}) if daily_index else None

    print("stock_daily mapped record:")
    print(json.dumps(daily_record, indent=2, ensure_ascii=False, default=str))
    print(f"intraday_1m candles: {len(intraday)}")
    print(f"security details records: {len(details)}")
    print(f"index list records: {len(indexes)}")
    print("index_daily mapped record:")
    print(json.dumps(index_record, indent=2, ensure_ascii=False, default=str))

    if args.write:
        db = SupabaseClient()
        if raw_daily:
            db.upsert_raw_daily([raw_daily])
        if daily_record:
            db.upsert_stock_daily([daily_record])
        if index_record:
            db.upsert_index_daily([index_record])
        print("Wrote daily/index records. Intraday is intentionally not written by this smoke script.")


if __name__ == "__main__":
    main()
