from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from typing import Any

from src.database.client import SupabaseClient
from src.pipeline.date_utils import parse_ddmmyyyy
from src.pipeline.symbol_scope import resolve_symbol_scope, symbol_scope_summary
from src.validation.intraday_validator import validate_intraday_batch

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UTC_TZ = ZoneInfo("UTC")

# Data-quality heuristics, not official SSI completeness rules. SSI can omit a
# minute candle when no trade occurs, so short isolated gaps remain observable
# without failing ingest. Structural coverage loss still needs investigation.
LONG_CONTINUOUS_GAP_MINUTES = 15
MAX_TOTAL_EMPTY_MINUTES = 30
SESSION_EDGE_TOLERANCE_MINUTES = 15
MORNING_START = time(9, 0)
MORNING_END = time(11, 30)
AFTERNOON_START = time(13, 0)
AFTERNOON_COVERAGE_END = time(14, 29)


def _count_query(db: SupabaseClient, table: str, select: str = '*', **eq) -> int:
    query = db.client.table(table).select(select, count='exact')
    for key, value in eq.items():
        query = query.eq(key, value)
    result = db._with_retry(lambda: query.limit(1).execute(), action_name=f"count {table}")
    return result.count or 0


def _count_time_range_query(db: SupabaseClient, table: str, start: str, end: str, select: str = '*', **eq) -> int:
    query = db.client.table(table).select(select, count='exact').gte('time', start).lt('time', end)
    for key, value in eq.items():
        query = query.eq(key, value)
    result = db._with_retry(lambda: query.limit(1).execute(), action_name=f"count {table} time range")
    return result.count or 0


def _vn_utc_range(validated) -> tuple[str, str]:
    start_vn = datetime.combine(validated.date, time.min, tzinfo=VN_TZ)
    end_vn = start_vn + timedelta(days=1)
    return start_vn.astimezone(UTC_TZ).strftime('%Y-%m-%dT%H:%M:%SZ'), end_vn.astimezone(UTC_TZ).strftime('%Y-%m-%dT%H:%M:%SZ')


def _fetch_daily_symbols(db: SupabaseClient, date_iso: str, symbols: list[str] | None = None, page_size: int = 1000) -> set[str]:
    if page_size <= 0:
        raise ValueError('page_size must be greater than zero')
    rows: list[dict] = []
    offset = 0
    previous_page: tuple | None = None
    page_number = 0
    while True:
        query = db.client.table('stock_daily').select('symbol').eq('trading_date', date_iso)
        if symbols is not None:
            query = query.in_('symbol', symbols)
        query = query.order('symbol').range(offset, offset + page_size - 1)
        page_number += 1
        result = db._with_retry(lambda q=query: q.execute(), action_name=f'fetch stock_daily symbols page={page_number} offset={offset}')
        page = result.data or []
        if not page:
            break
        identity = tuple(row.get('symbol') for row in page)
        if identity == previous_page:
            raise RuntimeError(f'Repeated PostgREST page table=stock_daily scope={date_iso} page={page_number} offset={offset} returned={len(page)}')
        previous_page = identity
        rows.extend(page)
        offset += len(page)
    return {row['symbol'] for row in rows}


def _fetch_intraday_rows(db: SupabaseClient, start: str, end: str, symbols: list[str] | None = None, page_size: int = 1000) -> list[dict]:
    if page_size <= 0:
        raise ValueError('page_size must be greater than zero')
    rows: list[dict] = []
    offset = 0
    page_number = 0
    previous_page: tuple | None = None
    while True:
        query = (db.client.table('stock_intraday')
            .select('symbol,time,timeframe')
            .gte('time', start).lt('time', end).eq('timeframe', '1m'))
        if symbols is not None:
            query = query.in_('symbol', symbols)
        query = query.order('symbol').order('time').range(offset, offset + page_size - 1)
        result = db._with_retry(lambda q=query: q.execute(), action_name=f'fetch stock_intraday completeness offset={offset}')
        page = result.data or []
        if not page:
            break
        page_number += 1
        identity = tuple((row.get('symbol'), row.get('time')) for row in page)
        if identity == previous_page:
            raise RuntimeError(f'Repeated PostgREST page table=stock_intraday scope={start}:{end} page={page_number} offset={offset} returned={len(page)}')
        previous_page = identity
        rows.extend(page)
        offset += len(page)
    return rows


def _symbol_intraday_summary(symbol: str, rows: list[dict], has_daily: bool) -> dict[str, Any]:
    times = [r.get('time') for r in rows if r.get('time')]
    duplicate_count = sum(count - 1 for count in Counter(times).values() if count > 1)
    records = [{"symbol": symbol, "time": t, "timeframe": "1m", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 0} for t in sorted(set(times))]
    validation = validate_intraday_batch(records)
    missing_interval_count = 0
    missing_minutes = 0
    longest_gap_minutes = 0
    for issue in validation.warnings:
        if issue.code == 'INTRADAY_MISSING_INTERVAL':
            missing_interval_count += 1
            actual = issue.actual_value or {}
            interval_minutes = int(actual.get('missing_minutes') or 0) if isinstance(actual, dict) else 0
            missing_minutes += interval_minutes
            longest_gap_minutes = max(longest_gap_minutes, interval_minutes)

    parsed_times = sorted(
        datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(VN_TZ)
        for value in set(times)
    )
    morning_times = [dt for dt in parsed_times if MORNING_START <= dt.time() <= MORNING_END]
    afternoon_times = [dt for dt in parsed_times if AFTERNOON_START <= dt.time()]
    first_candle_late = bool(
        parsed_times
        and parsed_times[0].time()
        > (datetime.combine(parsed_times[0].date(), MORNING_START) + timedelta(minutes=SESSION_EDGE_TOLERANCE_MINUTES)).time()
    )
    last_candle_early = bool(
        parsed_times
        and parsed_times[-1].time()
        < (datetime.combine(parsed_times[-1].date(), AFTERNOON_COVERAGE_END) - timedelta(minutes=SESSION_EDGE_TOLERANCE_MINUTES)).time()
    )
    structural_reasons = []
    if times and not morning_times:
        structural_reasons.append('missing_morning_session')
    if times and not afternoon_times:
        structural_reasons.append('missing_afternoon_session')
    if first_candle_late:
        structural_reasons.append('late_first_candle')
    if last_candle_early:
        structural_reasons.append('early_last_candle')
    if longest_gap_minutes >= LONG_CONTINUOUS_GAP_MINUTES:
        structural_reasons.append('long_continuous_gap')
    if missing_minutes >= MAX_TOTAL_EMPTY_MINUTES:
        structural_reasons.append('excessive_total_gap_minutes')

    gap_status = 'STRUCTURAL' if structural_reasons else ('OBSERVED' if missing_minutes else 'NONE')
    status = 'OK'
    if not has_daily or not times:
        status = 'MISSING'
    elif duplicate_count or structural_reasons:
        status = 'WARNING'
    return {
        "symbol": symbol,
        "stock_daily_present": has_daily,
        "intraday_candle_count": len(rows),
        "first_candle_time": min(times) if times else None,
        "last_candle_time": max(times) if times else None,
        "duplicate_count": duplicate_count,
        "missing_interval_count": missing_interval_count,
        "missing_minutes": missing_minutes,
        "empty_minute_bucket_count": missing_minutes,
        "longest_gap_minutes": longest_gap_minutes,
        "gap_status": gap_status,
        "structural_gap_reasons": structural_reasons,
        "status": status,
    }


def _resolve_check_scope(db: SupabaseClient, symbols):
    resolved, requested = resolve_symbol_scope(db, symbols)
    return resolved, requested, symbol_scope_summary(resolved, requested)


def check_daily_ingest(date: str, symbols: list[str] | tuple[str, ...] | None = None) -> dict:
    """Check only canonical stock_daily presence for one exact scope and date."""
    db = SupabaseClient()
    validated = parse_ddmmyyyy(date)
    resolved, requested, scope_summary = _resolve_check_scope(db, symbols)
    query_scope = resolved if requested is not None else None
    daily_present = _fetch_daily_symbols(db, validated.iso, query_scope)
    missing = [symbol for symbol in resolved if symbol not in daily_present]
    count = len(daily_present)
    status = 'FAILED' if not resolved or count == 0 else ('PARTIAL' if missing else 'OK')
    summary = {
        "date": validated.iso,
        **scope_summary,
        "stock_daily_count": count,
        "missing_stock_daily_count": len(missing),
        "missing_stock_daily_symbols": missing,
        "missing_stock_daily_symbols_sample": missing[:100],
        "status": status,
    }
    print(f"🔎 Daily ingest completeness for {date} ({validated.iso}) status={status}")
    return summary


def check_intraday_ingest(date: str, symbols: list[str] | tuple[str, ...] | None = None) -> dict:
    """Check only canonical 1m stock_intraday structural coverage."""
    db = SupabaseClient()
    validated = parse_ddmmyyyy(date)
    start, end = _vn_utc_range(validated)
    resolved, requested, scope_summary = _resolve_check_scope(db, symbols)
    query_scope = resolved if requested is not None else None
    rows = _fetch_intraday_rows(db, start, end, query_scope)
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_symbol[row.get('symbol')].append(row)
    # Intraday completeness is source-isolated; daily context is reported by the
    # ingest stage and is not queried here.
    per_symbol = [_symbol_intraday_summary(symbol, by_symbol.get(symbol, []), True) for symbol in resolved]
    missing = [symbol for symbol in resolved if not by_symbol.get(symbol)]
    incomplete = [
        {"symbol": item["symbol"], "candle_count": item["intraday_candle_count"],
         "missing_interval_count": item["missing_interval_count"], "missing_minutes": item["missing_minutes"]}
        for item in per_symbol if item["intraday_candle_count"] and item["status"] == 'WARNING'
    ]
    count = len(rows)
    status = 'FAILED' if not resolved or count == 0 else ('PARTIAL' if missing or incomplete else 'OK')
    summary = {
        "date": validated.iso,
        **scope_summary,
        "stock_intraday_count": count,
        "intraday_symbol_count": sum(bool(by_symbol.get(symbol)) for symbol in resolved),
        "missing_intraday_count": len(missing),
        "missing_intraday_symbols": missing,
        "missing_intraday_symbols_sample": missing[:100],
        "incomplete_intraday_count": len(incomplete),
        "incomplete_intraday_symbols": incomplete,
        "per_symbol": per_symbol,
        "status": status,
        "utc_range": {"start": start, "end": end},
    }
    print(f"🔎 Intraday ingest completeness for {date} ({validated.iso}) status={status}")
    return summary


def check_ingest(date: str, symbols: list[str] | tuple[str, ...] | None = None) -> dict:
    """Compatibility wrapper for combined backfill/refill callers."""
    daily = check_daily_ingest(date, symbols=symbols)
    intraday = check_intraday_ingest(date, symbols=symbols)
    db = SupabaseClient()
    validated = parse_ddmmyyyy(date)
    start, end = _vn_utc_range(validated)
    if daily["status"] == 'FAILED' or intraday["status"] == 'FAILED':
        status = 'FAILED'
    elif daily["status"] == 'PARTIAL' or intraday["status"] == 'PARTIAL':
        status = 'PARTIAL'
    else:
        status = 'OK'
    return {
        **daily,
        **{key: value for key, value in intraday.items() if key not in {"date", "symbol_scope", "requested_symbols", "symbols", "symbol_count", "status"}},
        "index_daily_count": 0,
        "foreign_trading_count": _count_query(db, 'stock_foreign_trading', trading_date=validated.iso),
        "orderbook_snapshot_count": _count_time_range_query(db, 'stock_orderbook_snapshot', start, end),
        "status": status,
        "utc_range": {"start": start, "end": end},
    }
