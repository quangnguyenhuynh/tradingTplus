#!/usr/bin/env python3
from __future__ import annotations
import argparse
from src.pipeline.fetch_one_day import fetch_daily_price, fetch_intraday_candles, fetch_one_day
from src.ssi.api import SSIApi

def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch/test one symbol for one day")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--date", required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True)
    group.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    symbol = args.symbol.upper()
    if args.write:
        count = fetch_one_day(symbol, args.date)
        print(f"Wrote {count} intraday candles for {symbol} {args.date}")
    else:
        ssi = SSIApi()
        daily = fetch_daily_price(ssi, symbol, args.date)
        candles = fetch_intraday_candles(ssi, symbol, args.date)
        print(f"Dry-run {symbol} {args.date}: daily_found={bool(daily)} intraday_candles={len(candles)}; no DB writes")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
