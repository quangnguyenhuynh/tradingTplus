"""Inclusive date-range backfill for persisted daily and intraday features."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from src.database.client import SupabaseClient

from .daily import compute_daily_features
from .intraday import (
    _resolve_as_of,
    aggregate_timeframe,
    compute_intraday_features,
    filter_closed_buckets,
)
from .policy import PERSISTED_INTRADAY_TIMEFRAMES, validate_intraday_persisted_timeframes
from .runtime import (
    VN_TZ,
    date_bounds_for_daily_context,
    fetch_stock_daily_rows,
    fetch_stock_intraday_paginated,
    filter_output_by_time,
    normalize_target_date,
    target_utc_bounds,
    upsert_feature_frame,
)


def normalize_feature_range(from_date, to_date) -> tuple[date, date]:
    start = normalize_target_date(from_date)
    end = normalize_target_date(to_date)
    if start > end:
        raise ValueError("from_date must be <= to_date")
    if end > datetime.now(VN_TZ).date():
        raise ValueError("to_date cannot be in the future")
    return start, end


def _resolve_symbols(db: SupabaseClient, symbols) -> list[str]:
    if symbols is None:
        result = db.get().table("stock_symbols").select("symbol").execute()
        symbols = [row["symbol"] for row in result.data]
    return list(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols))


def _summary(flow, start, end, symbols, timeframes, worker) -> dict:
    db = SupabaseClient()
    if not db.health_check():
        raise RuntimeError("Supabase health-check failed. Please check connection and credentials.")
    resolved_symbols = _resolve_symbols(db, symbols)
    records = {timeframe: 0 for timeframe in timeframes}
    errors = []
    total = 0
    successes = 0
    for symbol in resolved_symbols:
        try:
            total += worker(db, symbol, start, end, records)
            successes += 1
        except Exception as exc:
            errors.append({"symbol": symbol, "error": str(exc)})
    failed = len(errors)
    status = "FAILED" if failed == len(resolved_symbols) else ("PARTIAL" if failed else "OK")
    return {
        "flow": flow,
        "mode": "range",
        "from_date": start.isoformat(),
        "to_date": end.isoformat(),
        "requested_symbols": len(resolved_symbols),
        "successful_symbols": successes,
        "failed_symbols": failed,
        "total_records": total,
        "records_by_timeframe": records,
        "errors": errors,
        "status": status,
    }


def run_daily_feature_backfill(from_date, to_date, symbols=None, upsert_batch_size=1000) -> dict:
    """Compute with all prior daily history through to_date; write only the range."""
    start, end = normalize_feature_range(from_date, to_date)
    filter_start = target_utc_bounds(start)[0]
    filter_end = target_utc_bounds(end)[1]

    def worker(db, symbol, _start, _end, records):
        rows = fetch_stock_daily_rows(db, symbol, end_date=end)
        if not rows:
            return 0
        frame = compute_daily_features(pd.DataFrame(rows))
        output = filter_output_by_time(frame, filter_start, filter_end)
        count = upsert_feature_frame(db, symbol, "1d", output, upsert_batch_size)
        records["1d"] += count
        return count

    return _summary("features-daily-backfill", start, end, symbols, ("1d",), worker)


def run_intraday_feature_backfill(
    from_date,
    to_date,
    symbols=None,
    timeframes=None,
    upsert_batch_size=1000,
) -> dict:
    """Compute once through to_date from clean 1m; write only 15m/60m rows in range."""
    start, end = normalize_feature_range(from_date, to_date)
    normalized = validate_intraday_persisted_timeframes(
        timeframes or PERSISTED_INTRADAY_TIMEFRAMES
    )
    filter_start = target_utc_bounds(start)[0]
    filter_end = target_utc_bounds(end)[1]
    source_end = filter_end.strftime("%Y-%m-%dT%H:%M:%SZ")
    cutoff = _resolve_as_of(end, None)

    def worker(db, symbol, _start, _end, records):
        rows = fetch_stock_intraday_paginated(
            db,
            symbol,
            lt_time=source_end,
            order_desc=False,
        )
        if not rows:
            return 0
        bounds = date_bounds_for_daily_context(rows)
        daily_rows = fetch_stock_daily_rows(db, symbol, bounds[0], bounds[1]) if bounds else []
        source = pd.DataFrame(rows)
        total = 0
        for timeframe in normalized:
            aggregated = aggregate_timeframe(source, timeframe)
            closed = filter_closed_buckets(aggregated, timeframe, cutoff)
            computed = (
                compute_intraday_features(closed, timeframe, pd.DataFrame(daily_rows))
                if not closed.empty
                else closed
            )
            output = filter_output_by_time(computed, filter_start, filter_end)
            count = upsert_feature_frame(db, symbol, timeframe, output, upsert_batch_size)
            records[timeframe] += count
            total += count
        return total

    return _summary(
        "features-intraday-backfill",
        start,
        end,
        symbols,
        normalized,
        worker,
    )
