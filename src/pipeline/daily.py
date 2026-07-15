from datetime import timedelta, timezone
from typing import Any

from src.database.client import SupabaseClient
from src.ssi.api import SSIApi
from src.pipeline.fetch_one_day import fetch_daily_for_symbol_with_clients
from src.pipeline.index_data import fetch_daily_indexes, sync_indexes, sync_index_components
from src.pipeline.foreign_trading import fetch_foreign_for_symbol
from src.pipeline.date_utils import latest_previous_weekday, parse_ddmmyyyy, validate_safe_write_date

VN_TZ = timezone(timedelta(hours=7))


def _resolve_daily_date(date: str | None) -> str:
    if date is None:
        resolved = latest_previous_weekday().strftime("%d/%m/%Y")
        print(f"📆 Daily fetch defaulted to latest previous weekday: {resolved}")
        return resolved
    validated = parse_ddmmyyyy(date)
    validate_safe_write_date(validated)
    print(f"📆 Daily fetch: {validated.ddmmyyyy}")
    return validated.ddmmyyyy


def run_daily_ingest(date: str = None):
    """Ingest SSI end-of-day data only; does not ingest intraday candles or compute features."""
    date = _resolve_daily_date(date)
    db = SupabaseClient()
    symbols = db.get_symbols()
    if not symbols:
        print("❌ Chưa có dữ liệu symbols. Chạy 'python main.py init' trước!")
        return {
            'date': date,
            'symbol_count': 0,
            'daily_valid_count': 0,
            'total_daily_rows': 0,
            'total_candles': 0,
            'total_foreign': 0,
            'index_daily_count': 0,
            'error_count': 0,
            'errors': [],
            'status': 'FAILED',
        }

    ssi = SSIApi()
    sync_indexes(ssi=ssi, db=db)
    sync_index_components(None, ssi=ssi, db=db)
    total_daily_rows = 0
    total_foreign = 0
    errors: list[dict[str, Any]] = []
    for symbol in symbols:
        try:
            summary = fetch_daily_for_symbol_with_clients(ssi, db, symbol, date)
            total_daily_rows += int(summary.get('daily_rows') or 0)
            if summary.get('status') == 'FAILED':
                errors.append({'symbol': symbol, 'error': '; '.join(summary.get('errors') or ['daily ingest failed'])})
            foreign_record = fetch_foreign_for_symbol(ssi, symbol, date)
            if foreign_record:
                db.upsert_foreign([foreign_record])
                total_foreign += 1
        except Exception as e:
            errors.append({'symbol': symbol, 'error': str(e)})
            print(f"    ❌ {symbol}: {e}")

    index_count = fetch_daily_indexes(date, ssi=ssi, db=db)
    status = 'OK' if not errors else 'FAILED' if len(errors) >= len(symbols) else 'PARTIAL'
    print(f"\n✅ Hoàn thành daily ingest! stock_daily rows: {total_daily_rows}; foreign_trading: {total_foreign}; index_daily: {index_count}; errors: {len(errors)}")
    print("ℹ️ Intraday ingest and feature engine disabled in daily task.")
    return {
        'date': date,
        'symbol_count': len(symbols),
        'daily_valid_count': total_daily_rows,
        'total_daily_rows': total_daily_rows,
        'total_candles': 0,  # deprecated compatibility key; daily no longer writes intraday candles.
        'total_foreign': total_foreign,
        'index_daily_count': index_count,
        'error_count': len(errors),
        'errors': errors,
        'status': status,
    }


# Backward-compatible alias for older imports.
daily_run = run_daily_ingest
