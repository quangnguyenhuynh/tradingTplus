from __future__ import annotations

from datetime import datetime, timedelta

from src.database.client import SupabaseClient
from src.pipeline.date_utils import parse_ddmmyyyy


def _count_query(db: SupabaseClient, table: str, select: str = '*', **eq) -> int:
    query = db.client.table(table).select(select, count='exact')
    for key, value in eq.items():
        query = query.eq(key, value)
    result = db._with_retry(lambda: query.limit(1).execute(), action_name=f"count {table}")
    return result.count or 0


def _missing_stock_daily(db: SupabaseClient, symbols: list[str], date_iso: str) -> list[str]:
    result = db._with_retry(
        lambda: db.client.table('stock_daily').select('symbol').eq('trading_date', date_iso).execute(),
        action_name='missing stock_daily symbols',
    )
    present = {row['symbol'] for row in (result.data or [])}
    return [symbol for symbol in symbols if symbol not in present]


def check_ingest(date: str) -> dict:
    db = SupabaseClient()
    validated = parse_ddmmyyyy(date)
    date_iso = validated.iso
    start = datetime.combine(validated.date, datetime.min.time()).isoformat()
    end = datetime.combine(validated.date + timedelta(days=1), datetime.min.time()).isoformat()
    symbols = db.get_symbols()
    summary = {
        'symbol_count': len(symbols),
        'securities_count': _count_query(db, 'securities'),
        'stock_daily_count': _count_query(db, 'stock_daily', trading_date=date_iso),
        'index_daily_count': _count_query(db, 'index_daily', trading_date=date_iso),
        'foreign_trading_count': _count_query(db, 'foreign_trading', trading_date=date_iso),
        'orderbook_snapshot_count': 0,
        'stock_intraday_count': 0,
        'missing_stock_daily_symbols': [],
    }
    intraday = db._with_retry(
        lambda: db.client.table('stock_intraday').select('symbol', count='exact').gte('time', start).lt('time', end).eq('timeframe', '1m').limit(1).execute(),
        action_name='count stock_intraday',
    )
    summary['stock_intraday_count'] = intraday.count or 0
    orderbook = db._with_retry(
        lambda: db.client.table('orderbook_snapshot').select('symbol', count='exact').gte('time', start).lt('time', end).limit(1).execute(),
        action_name='count orderbook_snapshot',
    )
    summary['orderbook_snapshot_count'] = orderbook.count or 0
    summary['missing_stock_daily_symbols'] = _missing_stock_daily(db, symbols, date_iso)[:100]

    print(f"🔎 Ingest completeness for {date} ({date_iso})")
    for key, value in summary.items():
        if key != 'missing_stock_daily_symbols':
            print(f"  {key}: {value}")
    if summary['missing_stock_daily_symbols']:
        print("  ⚠️ Missing stock_daily symbols (first 100): " + ', '.join(summary['missing_stock_daily_symbols']))
    else:
        print("  ✅ No missing stock_daily symbols among current symbols list")
    return summary
