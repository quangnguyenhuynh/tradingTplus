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


def _fetch_daily_symbols(db: SupabaseClient, date_iso: str, symbols: list[str] | None = None) -> set[str]:
    query = db.client.table('stock_daily').select('symbol').eq('trading_date', date_iso)
    if symbols is not None:
        query = query.in_('symbol', symbols)
    result = db._with_retry(lambda: query.execute(), action_name='stock_daily symbols')
    return {row['symbol'] for row in (result.data or [])}


def _fetch_intraday_rows(db: SupabaseClient, start: str, end: str, symbols: list[str] | None = None, page_size: int = 1000) -> list[dict]:
    rows: list[dict] = []
    offset = 0
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
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
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


def check_ingest(date: str, symbols: list[str] | tuple[str, ...] | None = None) -> dict:
    db = SupabaseClient()
    validated = parse_ddmmyyyy(date)
    date_iso = validated.iso
    start, end = _vn_utc_range(validated)
    active_symbols, requested_symbols = resolve_symbol_scope(db, symbols)
    scope_summary = symbol_scope_summary(active_symbols, requested_symbols)
    query_scope = active_symbols if requested_symbols is not None else None
    daily_present = _fetch_daily_symbols(db, date_iso, query_scope)
    intraday_rows = _fetch_intraday_rows(db, start, end, query_scope)
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for row in intraday_rows:
        by_symbol[row.get('symbol')].append(row)

    per_symbol = [_symbol_intraday_summary(symbol, by_symbol.get(symbol, []), symbol in daily_present) for symbol in active_symbols]
    missing_daily = [s for s in active_symbols if s not in daily_present]
    missing_intraday = [s for s in active_symbols if not by_symbol.get(s)]
    incomplete = [
        {"symbol": r["symbol"], "candle_count": r["intraday_candle_count"], "missing_interval_count": r["missing_interval_count"], "missing_minutes": r["missing_minutes"]}
        for r in per_symbol if r["intraday_candle_count"] and r["status"] == 'WARNING'
    ]
    stock_daily_count = len(daily_present)
    stock_intraday_count = len(intraday_rows)
    if stock_daily_count == 0 or stock_intraday_count == 0:
        status = 'FAILED'
    elif missing_daily or missing_intraday or incomplete:
        status = 'PARTIAL'
    else:
        status = 'OK'
    summary = {
        "date": date_iso,
        **scope_summary,
        "stock_daily_count": stock_daily_count,
        "missing_stock_daily_count": len(missing_daily),
        "missing_stock_daily_symbols": missing_daily,
        "missing_stock_daily_symbols_sample": missing_daily[:100],
        "stock_intraday_count": stock_intraday_count,
        "intraday_symbol_count": len([s for s in active_symbols if by_symbol.get(s)]),
        "missing_intraday_count": len(missing_intraday),
        "missing_intraday_symbols": missing_intraday,
        "missing_intraday_symbols_sample": missing_intraday[:100],
        "incomplete_intraday_count": len(incomplete),
        "incomplete_intraday_symbols": incomplete,
        "per_symbol": per_symbol,
        "index_daily_count": _count_query(db, 'index_daily', trading_date=date_iso),
        "foreign_trading_count": _count_query(db, 'foreign_trading', trading_date=date_iso),
        "orderbook_snapshot_count": _count_time_range_query(db, 'orderbook_snapshot', start, end),
        "status": status,
        "utc_range": {"start": start, "end": end},
    }
    print(f"🔎 Ingest completeness for {date} ({date_iso}) status={status}")
    return summary
