#!/usr/bin/env python3
"""Run end-to-end pipeline demo with clear step logs.

Flow:
1) init symbols
2) test fetch one symbol/day
3) daily run for a day
4) optional backfill window
5) optional signal engine

Usage:
  python scripts/run_e2e_demo.py --date 20/05/2026 --symbol SSI
  python scripts/run_e2e_demo.py --date 20/05/2026 --symbol SSI --with-backfill --from-date 2026-05-19 --to-date 2026-05-20
  python scripts/run_e2e_demo.py --date 20/05/2026 --symbol SSI --with-signal
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.init_symbols import init_symbols
from src.pipeline.fetch_one_day import fetch_one_day
from src.pipeline.daily import daily_run
from src.pipeline.backfill import backfill
from src.engine.signal_engine import run_signal_engine
from src.engine.feature_engine import run_feature_engine
from src.pipeline.date_utils import parse_ddmmyyyy, parse_iso_date, validate_not_future

REQUIRED_ENV_KEYS = [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "SSI_CONSUMER_ID",
    "SSI_CONSUMER_SECRET",
]


def _step(name: str):
    print(f"\n{'=' * 72}\n🚀 STEP: {name}\n{'=' * 72}")
    started = time.time()

    def _finish(extra: str = ""):
        elapsed = time.time() - started
        suffix = f" | {extra}" if extra else ""
        print(f"✅ DONE: {name} ({elapsed:.2f}s){suffix}")

    return _finish


def _require_env() -> None:
    missing = [k for k in REQUIRED_ENV_KEYS if not os.getenv(k)]
    if missing:
        print("❌ Missing required environment variables:")
        for key in missing:
            print(f"   - {key}")
        print("\nHãy set .env trước khi chạy script này.")
        sys.exit(2)


def _to_iso_date(ddmmyyyy: str) -> str:
    return datetime.strptime(ddmmyyyy, "%d/%m/%Y").strftime("%Y-%m-%d")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run E2E tradingTplus demo flow")
    parser.add_argument("--date", default=None, help="DD/MM/YYYY. Required for steps that write daily/fetch/signal data.")
    parser.add_argument("--symbol", default="SSI", help="Symbol for one-day test fetch")
    parser.add_argument("--skip-init", action="store_true", help="Skip init_symbols step")
    parser.add_argument("--skip-test", action="store_true", help="Skip fetch_one_day test step")
    parser.add_argument("--skip-daily", action="store_true", help="Skip daily_run step")

    parser.add_argument("--with-backfill", action="store_true", help="Run optional backfill step")
    parser.add_argument("--from-date", default=None, help="Backfill from date YYYY-MM-DD")
    parser.add_argument("--to-date", default=None, help="Backfill to date YYYY-MM-DD")

    parser.add_argument("--with-feature", action="store_true", help="Run optional run_feature_engine(symbols) step")
    parser.add_argument("--feature-symbols", nargs="*", default=None, help="Symbols for run_feature_engine, e.g. --feature-symbols SSI FPT")
    parser.add_argument("--with-signal", action="store_true", help="Run optional signal engine step")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _require_env()

    date = args.date
    if date:
        try:
            validated_date = parse_ddmmyyyy(date)
            validate_not_future(validated_date)
        except ValueError as exc:
            raise SystemExit(f"❌ {exc}") from exc
    elif not args.skip_test or not args.skip_daily or args.with_signal:
        raise SystemExit("❌ --date DD/MM/YYYY is required for E2E steps that write/fetch daily data. Use --skip-test --skip-daily if you only want init/feature checks.")

    print("📌 E2E DEMO CONFIG")
    print(f"   date       : {date or 'not provided'}")
    print(f"   symbol     : {args.symbol}")
    print(f"   with_backfill: {args.with_backfill}")
    print(f"   with_feature : {args.with_feature}")
    print(f"   feature_symbols: {args.feature_symbols}")
    print(f"   with_signal  : {args.with_signal}")

    if not args.skip_init:
        done = _step("init_symbols()")
        init_symbols()
        done()

    if not args.skip_test:
        done = _step(f"fetch_one_day(symbol={args.symbol}, date={date or '[default required by function]'})")
        if date is None:
            raise SystemExit("❌ Step fetch_one_day cần --date DD/MM/YYYY để chạy rõ ràng")
        count = fetch_one_day(args.symbol, date)
        done(extra=f"candles={count}")

    if not args.skip_daily:
        done = _step(f"daily_run(date={date})")
        daily_run(date)
        done()

    if args.with_backfill:
        if not args.from_date or not args.to_date:
            if not date:
                raise SystemExit("❌ Nếu --with-backfill mà không truyền from/to thì cần --date")
            one_day = _to_iso_date(date)
            from_date = one_day
            to_date = one_day
        else:
            try:
                from_validated = parse_iso_date(args.from_date)
                to_validated = parse_iso_date(args.to_date)
                validate_not_future(from_validated)
                validate_not_future(to_validated)
            except ValueError as exc:
                raise SystemExit(f"❌ {exc}") from exc
            from_date = from_validated.iso
            to_date = to_validated.iso

        done = _step(f"backfill(from_date={from_date}, to_date={to_date})")
        backfill(from_date, to_date)
        done()


    if args.with_feature:
        symbols = args.feature_symbols
        done = _step(f"run_feature_engine(symbols={symbols})")
        feature_count = run_feature_engine(symbols)
        done(extra=f"feature_records={feature_count}")

    if args.with_signal:
        target_date = _to_iso_date(date) if date else datetime.now().strftime("%Y-%m-%d")
        done = _step(f"run_signal_engine(target_date={target_date})")
        run_signal_engine(target_date)
        done()

    print("\n🎉 E2E demo flow completed.")


if __name__ == "__main__":
    main()
