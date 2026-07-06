#!/usr/bin/env python
"""Smoke-test complete SSI ingest mapping.

Default mode is read-only. Writes require --write plus an explicit --date and pass
weekend/future-date guards unless --force is provided.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.client import SupabaseClient
from src.pipeline.date_utils import latest_previous_weekday, parse_ddmmyyyy, validate_safe_write_date
from src.pipeline.fetch_one_day import build_raw_daily_record, build_stock_daily_record
from src.pipeline.index_data import build_index_daily_record
from src.ssi.api import SSIApi


def _resolve_date(date_arg: str | None, *, write: bool, force: bool):
    if date_arg:
        selected = parse_ddmmyyyy(date_arg)
        print(f"📅 Using explicit smoke-test date: {selected.ddmmyyyy} ({selected.iso})")
    else:
        if write:
            raise SystemExit("❌ --write requires explicit --date DD/MM/YYYY to avoid accidental default-date writes.")
        fallback = latest_previous_weekday()
        selected = parse_ddmmyyyy(fallback.strftime("%d/%m/%Y"))
        print(f"📅 No --date supplied; read-only smoke test uses latest previous weekday: {selected.ddmmyyyy} ({selected.iso})")
    if write:
        try:
            validate_safe_write_date(selected, force=force)
        except ValueError as exc:
            raise SystemExit(f"❌ Refusing smoke-test write: {exc}. Pass --force only if this is intentional.") from exc
    return selected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only by default smoke test for complete SSI ingest mapping.")
    parser.add_argument("--symbol", default="SSI", help="Symbol to fetch for smoke test; default is SSI and read-only unless --write is passed.")
    parser.add_argument("--date", default=None, help="DD/MM/YYYY. Required when --write is used; read-only mode defaults to latest previous weekday.")
    parser.add_argument("--index-code", default="VNINDEX", help="Index code to fetch for DailyIndex smoke test.")
    parser.add_argument("--write", action="store_true", help="Persist raw_daily, stock_daily, and index_daily only. Disabled by default.")
    parser.add_argument("--write-intraday", action="store_true", help="Also persist raw_intraday and stock_intraday. Requires --write.")
    parser.add_argument("--force", action="store_true", help="Allow writes for weekend or future dates. Still requires explicit --date with --write.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.write_intraday and not args.write:
        raise SystemExit("❌ --write-intraday requires --write.")

    selected = _resolve_date(args.date, write=args.write, force=args.force)
    ssi_date = selected.ddmmyyyy
    symbol = args.symbol.upper()

    print("🔎 SSI COMPLETE INGEST SMOKE TEST")
    print(f"   mode       : {'WRITE' if args.write else 'READ-ONLY'}")
    print(f"   symbol     : {symbol}")
    print(f"   date       : {ssi_date} ({selected.iso})")
    print(f"   index_code : {args.index_code}")
    print(f"   intraday write: {args.write_intraday}")

    ssi = SSIApi()
    daily = ssi.get_daily_price(symbol, ssi_date)
    daily_record = build_stock_daily_record(symbol, ssi_date, daily or {}) if daily else None
    raw_daily = build_raw_daily_record(symbol, ssi_date, daily or {}) if daily else None
    intraday = ssi.get_intraday(symbol, ssi_date)
    details = ssi.get_security_details(symbol=symbol)
    indexes = ssi.get_index_list()
    daily_index = ssi.get_daily_index(args.index_code, ssi_date)
    index_record = build_index_daily_record(args.index_code, ssi_date, daily_index or {}) if daily_index else None

    print("\nstock_daily mapped record:")
    print(json.dumps(daily_record, indent=2, ensure_ascii=False, default=str))
    print(f"intraday_1m candles fetched (not written unless --write-intraday): {len(intraday)}")
    print(f"security details records: {len(details)}")
    print(f"index list records: {len(indexes)}")
    print("index_daily mapped record:")
    print(json.dumps(index_record, indent=2, ensure_ascii=False, default=str))

    if not args.write:
        print("\n✅ Read-only smoke test completed; no Supabase writes were attempted.")
        return

    try:
        validate_safe_write_date(selected, force=args.force)
    except ValueError as exc:
        raise SystemExit(f"❌ Refusing smoke-test write: {exc}. Pass --force only if this is intentional.") from exc
    target_tables = ["raw_daily", "stock_daily", "index_daily"]
    if args.write_intraday:
        target_tables.extend(["raw_intraday", "stock_intraday"])
    print("\n⚠️  WRITE CONFIRMATION")
    print(f"   symbol: {symbol}")
    print(f"   date  : {ssi_date} ({selected.iso})")
    print(f"   tables: {', '.join(target_tables)}")
    print("   safety: weekend/future guard passed" + (" with --force" if args.force else ""))

    db = SupabaseClient()
    if raw_daily:
        db.upsert_raw_daily([raw_daily])
        print("✅ Wrote raw_daily")
    if daily_record:
        db.upsert_stock_daily([daily_record])
        print("✅ Wrote stock_daily")
    if index_record:
        db.upsert_index_daily([index_record])
        print("✅ Wrote index_daily")
    if args.write_intraday:
        from src.pipeline.fetch_one_day import build_intraday_records, save_intraday_records

        raw_intraday, clean_intraday = build_intraday_records(symbol, ssi_date, daily or {}, intraday)
        count = save_intraday_records(db, raw_intraday, clean_intraday)
        print(f"✅ Wrote intraday rows: {count}")
    else:
        print("ℹ️ Intraday was fetched for validation but not written. Pass --write-intraday to persist it.")
    print("✅ Smoke-test writes completed.")


if __name__ == "__main__":
    main()
