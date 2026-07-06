#!/usr/bin/env python3
"""Backfill NULL stock_intraday.value with BIGINT-safe close * volume values."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.client import SupabaseClient
from src.intraday_value import calculate_trade_value

logger = logging.getLogger(__name__)


def _build_query(db: SupabaseClient, symbol: str | None, start: str | None, end: str | None, page_size: int):
    query = (
        db.get()
        .table("stock_intraday")
        .select("symbol,timeframe,time,close,volume,value")
        .is_("value", "null")
        .order("time", desc=False)
        .limit(page_size)
    )
    if symbol:
        query = query.eq("symbol", symbol)
    if start:
        query = query.gte("time", start)
    if end:
        query = query.lte("time", end)
    return query


def _log_samples(rows: list[dict[str, Any]], updates: list[dict[str, Any]]) -> None:
    update_by_key = {
        (row["symbol"], row.get("timeframe", "1m"), row["time"]): row["value"]
        for row in updates
    }
    for row in rows[:5]:
        key = (row["symbol"], row.get("timeframe", "1m"), row["time"])
        value = update_by_key.get(key)
        logger.info(
            "backfill sample symbol=%s timestamp=%s close=%s volume=%s value=%s type(value)=%s",
            row.get("symbol"),
            row.get("time"),
            row.get("close"),
            row.get("volume"),
            value,
            type(value).__name__,
        )


def backfill_stock_intraday_value(
    symbol: str | None = None,
    start: str | None = None,
    end: str | None = None,
    page_size: int = 500,
    dry_run: bool = False,
) -> int:
    db = SupabaseClient()
    total_updated = 0

    while True:
        result = db._with_retry(
            lambda: _build_query(db, symbol, start, end, page_size).execute(),
            action_name="fetch stock_intraday null value rows",
        )
        rows = result.data or []
        if not rows:
            break

        updates = []
        for row in rows:
            value = calculate_trade_value(row.get("close"), row.get("volume"))
            if value is None:
                continue
            updates.append({
                "symbol": row["symbol"],
                "timeframe": row.get("timeframe", "1m"),
                "time": row["time"],
                "value": value,
            })

        _log_samples(rows, updates)
        if not updates:
            break

        if dry_run:
            total_updated += len(updates)
            break

        for update in updates:
            db._with_retry(
                lambda payload=update: (
                    db.get()
                    .table("stock_intraday")
                    .update({"value": payload["value"]})
                    .eq("symbol", payload["symbol"])
                    .eq("timeframe", payload["timeframe"])
                    .eq("time", payload["time"])
                    .execute()
                ),
                action_name=f"update stock_intraday value {update['symbol']} {update['time']}",
            )
        total_updated += len(updates)

        if len(rows) < page_size:
            break

    logger.info("Backfilled %s stock_intraday.value rows", total_updated)
    return total_updated


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", help="Optional symbol, e.g. SSI")
    parser.add_argument("--start", help="Optional inclusive start timestamp/date")
    parser.add_argument("--end", help="Optional inclusive end timestamp/date")
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    backfill_stock_intraday_value(
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        page_size=args.page_size,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
