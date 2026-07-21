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
from src.pipeline.daily_mapper import build_raw_daily_record, build_stock_daily_record
from src.pipeline.index_data import build_index_daily_record, map_index_record
from src.pipeline.init_symbols import map_security_record
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


def _fetch_index_list(ssi: SSIApi) -> list[dict]:
    indexes = ssi.get_index_list()
    if indexes:
        return indexes
    print("⚠️ IndexList without exchange returned 0 rows; retrying HOSE/HNX/UPCOM.")
    for exchange in ("HOSE", "HNX", "UPCOM"):
        indexes.extend(ssi.get_index_list(exchange=exchange))
    return indexes


def _candidate_index_codes(requested: str, mapped_indexes: list[dict]) -> list[str]:
    requested_upper = requested.upper()
    candidates = [requested]
    for record in mapped_indexes:
        code = str(record.get("index_code") or "")
        name = str(record.get("index_name") or "")
        if not code:
            continue
        haystack = f"{code} {name}".upper().replace("-", "")
        if requested_upper.replace("-", "") in haystack and code not in candidates:
            candidates.append(code)
    for record in mapped_indexes[:10]:
        code = str(record.get("index_code") or "")
        if code and code not in candidates:
            candidates.append(code)
    return candidates


def _fetch_daily_index_with_fallback(ssi: SSIApi, requested: str, date: str, mapped_indexes: list[dict]) -> tuple[str, dict | None, dict | None]:
    last_raw: dict | None = None
    for code in _candidate_index_codes(requested, mapped_indexes):
        raw = ssi.get_daily_index_raw(code, date)
        last_raw = raw
        items = ssi._extract_items(raw or {})
        print(f"DailyIndex attempt index_code={code}: raw_items={len(items)}")
        if items:
            return code, items[0], raw
    return requested, None, last_raw


def _warn_empty(section: str) -> None:
    print(f"⚠️ WARNING: --write requested but {section} has no mapped records; nothing will be written for this section.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only by default smoke test for complete SSI ingest mapping.")
    parser.add_argument("--symbol", default="SSI", help="Symbol to fetch for smoke test; default is SSI and read-only unless --write is passed.")
    parser.add_argument("--date", default=None, help="DD/MM/YYYY. Required when --write is used; read-only mode defaults to latest previous weekday.")
    parser.add_argument("--index-code", default="VNINDEX", help="Index code to fetch for DailyIndex smoke test.")
    parser.add_argument("--write", action="store_true", help="Persist raw_daily, stock_daily, securities, indexes, and index_daily. Disabled by default.")
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

    security_details = ssi.get_security_details(symbol=symbol)
    security_records = [record for record in (map_security_record(row) for row in security_details) if record]
    print(f"fetched security detail count: {len(security_details)}")
    print(f"mapped securities count: {len(security_records)}")

    index_rows = _fetch_index_list(ssi)
    index_records = [record for record in (map_index_record(row) for row in index_rows) if record]
    print(f"fetched index list count: {len(index_rows)}")
    print(f"mapped indexes count: {len(index_records)}")

    accepted_index_code, daily_index, daily_index_raw = _fetch_daily_index_with_fallback(ssi, args.index_code, ssi_date, index_records)
    index_record = build_index_daily_record(accepted_index_code, ssi_date, daily_index or {}) if daily_index else None
    if daily_index is None:
        print("⚠️ WARNING: DailyIndex returned no mapped item. Last raw DailyIndex response:")
        print(json.dumps(daily_index_raw, indent=2, ensure_ascii=False, default=str))
    elif accepted_index_code != args.index_code:
        print(f"ℹ️ DailyIndex accepted fallback index_code={accepted_index_code} for requested {args.index_code}")

    print("\nstock_daily mapped record:")
    print(json.dumps(daily_record, indent=2, ensure_ascii=False, default=str))
    print(f"intraday_1m candles fetched (not written unless --write-intraday): {len(intraday)}")
    print("index_daily mapped record:")
    print(json.dumps(index_record, indent=2, ensure_ascii=False, default=str))

    if not args.write:
        print("\n✅ Read-only smoke test completed; no Supabase writes were attempted.")
        return

    if not args.force and daily_record is None and index_record is None:
        raise SystemExit("❌ Refusing smoke-test write: no stock_daily or index_daily data for this date (holiday/no trading data). Pass --force only if master-data-only write is intentional.")

    try:
        validate_safe_write_date(selected, force=args.force)
    except ValueError as exc:
        raise SystemExit(f"❌ Refusing smoke-test write: {exc}. Pass --force only if this is intentional.") from exc
    target_tables = ["raw_daily", "stock_daily", "securities", "indexes", "index_daily"]
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
        print("✅ Wrote raw_daily: 1")
    else:
        _warn_empty("raw_daily")
    if daily_record:
        db.upsert_stock_daily([daily_record])
        print("✅ Wrote stock_daily: 1")
    else:
        _warn_empty("stock_daily")
    if security_records:
        db.upsert_securities(security_records)
        print(f"✅ written securities count: {len(security_records)}")
    else:
        _warn_empty("securities")
    if index_records:
        db.upsert_indexes(index_records)
        print(f"✅ written indexes count: {len(index_records)}")
    else:
        _warn_empty("indexes")
    if index_record:
        db.upsert_index_daily([index_record])
        print("✅ Wrote index_daily: 1")
    else:
        _warn_empty("index_daily")
    if args.write_intraday:
        from src.pipeline.intraday_mapper import build_intraday_records
        from src.pipeline.intraday_persistence import save_intraday_records

        raw_intraday, clean_intraday = build_intraday_records(symbol, ssi_date, daily or {}, intraday)
        count = save_intraday_records(db, raw_intraday, clean_intraday)
        print(f"✅ Wrote intraday rows: {count}")
    else:
        print("ℹ️ Intraday was fetched for validation but not written. Pass --write-intraday to persist it.")
    print("✅ Smoke-test writes completed.")


if __name__ == "__main__":
    main()
