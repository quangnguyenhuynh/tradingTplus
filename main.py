#!/usr/bin/env python3
"""
Trading Pipeline - SSI to Supabase

Cách dùng:
    python main.py init | sync-master-data
    python main.py backfill [from_date] [to_date]   # YYYY-MM-DD
    python main.py daily [DD/MM/YYYY]               # mặc định: latest previous weekday
    python main.py snapshot-orderbook [--debug] [--timeout SEC] [SYMBOL ...]
    python main.py snapshot-stream [--debug] [--timeout SEC] [--indexes CSV] [--write|--no-write] [--limit N] [SYMBOL ...]
    python main.py check-ingest DD/MM/YYYY
    python main.py features [full|incremental] [--timeframes 1m 5m 15m] [--symbols SSI HPG FPT]
    python main.py eod-dry-run [DD/MM/YYYY] [--symbols SSI HPG] [--timeframes 1m 5m] [--json]
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
    from src.pipeline.orderbook_snapshot import snapshot_orderbook_from_stream

    debug = False
    timeout = None
    symbols: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--debug":
            debug = True
        elif arg == "--timeout":
            if i + 1 >= len(args):
                _print_usage_error("--timeout cần số giây")
                return
            timeout = int(args[i + 1])
            i += 1
        else:
            symbols.append(arg.upper())
        i += 1
    if not symbols:
        symbols = None
    count = snapshot_orderbook_from_stream(symbols=symbols or [], timeout_sec=timeout, write=True, debug=debug) if symbols else snapshot_orderbook(symbols=None)
    print(f"✅ Snapshot orderbook complete: {count} records")


def run_snapshot_stream(args: list[str]) -> None:
    from src.database.client import SupabaseClient
    from src.pipeline.streaming_snapshot import snapshot_market_stream

    debug = False
    timeout = 60
    indexes = ["VNINDEX", "VN30"]
    write = True
    limit = 20
    symbols: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--debug":
            debug = True
        elif arg == "--timeout":
            if i + 1 >= len(args):
                _print_usage_error("--timeout cần số giây")
                return
            timeout = int(args[i + 1]); i += 1
        elif arg == "--indexes":
            if i + 1 >= len(args):
                _print_usage_error("--indexes cần CSV, ví dụ VNINDEX,VN30")
                return
            indexes = [x.strip().upper() for x in args[i + 1].split(",") if x.strip()]; i += 1
        elif arg == "--write":
            write = True
        elif arg == "--no-write":
            write = False
        elif arg == "--limit":
            if i + 1 >= len(args):
                _print_usage_error("--limit cần số lượng")
                return
            limit = int(args[i + 1]); i += 1
        else:
            symbols.append(arg.upper())
        i += 1
    if not symbols:
        symbols = [s.upper() for s in SupabaseClient().get_symbols()[:limit]]
    summary = snapshot_market_stream(symbols=symbols[:limit] if limit else symbols, indexes=indexes, timeout_sec=timeout, write=write, debug=debug)
    print(f"✅ Snapshot stream complete: {summary}")

def run_features(args: list[str]) -> None:
    from src.engine.feature_engine import run_feature_engine

    mode = "incremental"
    timeframes = ["1m", "5m", "15m"]
    symbols = None

    i = 0
    if args and args[0] in {"full", "incremental"}:
        mode = args[0]
        i = 1

    while i < len(args):
        arg = args[i]
        if arg == "--timeframes":
            i += 1
            values = []
            while i < len(args) and not args[i].startswith("--"):
                values.append(args[i])
                i += 1
            if not values:
                _print_usage_error("--timeframes cần ít nhất một timeframe")
                return
            timeframes = values
            continue
        if arg == "--symbols":
            i += 1
            values = []
            while i < len(args) and not args[i].startswith("--"):
                values.append(args[i].upper())
                i += 1
            if not values:
                _print_usage_error("--symbols cần ít nhất một mã")
                return
            symbols = values
            continue
        _print_usage_error(f"Không biết tham số features: {arg}")
        return

    total = run_feature_engine(symbols=symbols, mode=mode, timeframes=timeframes)
    print(f"✅ Feature engine complete: {total} records")


def run_eod_dry_run_command(args: list[str]) -> None:
    from src.pipeline.eod_dry_run import DEFAULT_SYMBOLS, DEFAULT_TIMEFRAMES, run_eod_dry_run

    date = None
    symbols = DEFAULT_SYMBOLS
    timeframes = DEFAULT_TIMEFRAMES
    json_output = False

    i = 0
    if args and not args[0].startswith("--"):
        date = args[0]
        i = 1

    while i < len(args):
        arg = args[i]
        if arg == "--symbols":
            i += 1
            values = []
            while i < len(args) and not args[i].startswith("--"):
                values.append(args[i].upper())
                i += 1
            if not values:
                _print_usage_error("--symbols cần ít nhất một mã")
                return
            symbols = values
            continue
        if arg == "--timeframes":
            i += 1
            values = []
            while i < len(args) and not args[i].startswith("--"):
                values.append(args[i])
                i += 1
            if not values:
                _print_usage_error("--timeframes cần ít nhất một timeframe")
                return
            timeframes = values
            continue
        if arg == "--json":
            json_output = True
            i += 1
            continue
        _print_usage_error(f"Không biết tham số eod-dry-run: {arg}")
        return

    run_eod_dry_run(date=date, symbols=symbols, timeframes=timeframes, json_output=json_output)


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
    elif cmd == "snapshot-stream":
        run_snapshot_stream(args)
    elif cmd == "check-ingest":
        run_check_ingest(args)
    elif cmd == "features":
        run_features(args)
    elif cmd == "eod-dry-run":
        run_eod_dry_run_command(args)
    elif cmd == "test":
        run_test(args)
    else:
        _print_usage_error(f"Không biết lệnh: {cmd}")


if __name__ == "__main__":
    main()
