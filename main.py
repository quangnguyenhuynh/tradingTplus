#!/usr/bin/env python3
"""
Trading Pipeline - SSI to Supabase

Cách dùng:
    python main.py init | sync-master-data
    python main.py backfill [from_date] [to_date]   # YYYY-MM-DD
    python main.py daily [DD/MM/YYYY]               # mặc định: latest previous weekday
    python main.py snapshot-orderbook [SYMBOL ...]
    python main.py check-ingest DD/MM/YYYY
    python main.py test [SYMBOL] [DD/MM/YYYY]
"""

import sys
from datetime import datetime, timedelta, timezone
from src.pipeline import init_symbols, backfill, daily_run, fetch_one_day
from src.pipeline.orderbook_snapshot import snapshot_orderbook
from src.pipeline.ingest_check import check_ingest

VN_TZ = timezone(timedelta(hours=7))


def _today_vn() -> datetime:
    return datetime.now(VN_TZ)


def _is_yyyy_mm_dd(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _print_usage_error(message: str) -> None:
    print(f"❌ {message}")
    print(__doc__)


def run_backfill(args: list[str]) -> None:
    from_date = args[0] if len(args) >= 1 else "2023-01-01"
    to_date = args[1] if len(args) >= 2 else _today_vn().strftime("%Y-%m-%d")

    if not _is_yyyy_mm_dd(from_date) or not _is_yyyy_mm_dd(to_date):
        _print_usage_error("backfill yêu cầu format YYYY-MM-DD")
        return

    if from_date > to_date:
        _print_usage_error("from_date phải nhỏ hơn hoặc bằng to_date")
        return

    print(f"🚀 Backfill từ {from_date} -> {to_date}")
    backfill(from_date, to_date)


def run_daily(args: list[str]) -> None:
    date = args[0] if args else None
    daily_run(date)


def run_snapshot_orderbook(args: list[str]) -> None:
    debug = "--debug" in args
    clean_args = [arg for arg in args if arg != "--debug"]
    symbols = [arg.upper() for arg in clean_args] if clean_args else None
    count = snapshot_orderbook(symbols=symbols, debug=debug)
    print(f"✅ Snapshot orderbook complete: {count} records")


def run_check_ingest(args: list[str]) -> None:
    if not args:
        _print_usage_error("check-ingest yêu cầu DD/MM/YYYY")
        return
    check_ingest(args[0])


def run_test(args: list[str]) -> None:
    symbol = args[0] if len(args) >= 1 else "SSI"
    date = args[1] if len(args) >= 2 else (_today_vn() - timedelta(days=1)).strftime("%d/%m/%Y")

    print(f"🧪 Test fetch: symbol={symbol}, date={date}")
    count = fetch_one_day(symbol, date)
    print(f"✅ Đã lưu {count} candles cho {symbol}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd in ("init", "sync-master-data"):
        init_symbols()
    elif cmd == "backfill":
        run_backfill(args)
    elif cmd == "daily":
        run_daily(args)
    elif cmd == "snapshot-orderbook":
        run_snapshot_orderbook(args)
    elif cmd == "check-ingest":
        run_check_ingest(args)
    elif cmd == "test":
        run_test(args)
    else:
        _print_usage_error(f"Không biết lệnh: {cmd}")


if __name__ == "__main__":
    main()
