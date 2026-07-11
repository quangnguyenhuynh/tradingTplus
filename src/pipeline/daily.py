from datetime import datetime, timedelta, timezone
from src.database.client import SupabaseClient
from src.ssi.api import SSIApi
from src.pipeline.fetch_one_day import fetch_one_day_with_clients
from src.pipeline.index_data import fetch_daily_indexes, sync_indexes, sync_index_components
from src.pipeline.foreign_trading import fetch_foreign_for_symbol
from src.pipeline.date_utils import latest_previous_weekday

VN_TZ = timezone(timedelta(hours=7))


def run_daily_ingest(date: str = None):
    """Ingest SSI end-of-day data only; does not compute features/signals/backtests.

    Flow: SSI API -> raw_daily -> stock_daily -> raw_intraday 1m ->
    stock_intraday 1m -> foreign_trading -> index_daily.

    Args:
        date: DD/MM/YYYY (None = latest previous weekday)
    """
    if date is None:
        date = latest_previous_weekday().strftime("%d/%m/%Y")
        print(f"📆 Daily fetch defaulted to latest previous weekday: {date}")
    else:
        print(f"📆 Daily fetch: {date}")
    
    db = SupabaseClient()
    symbols = db.get_symbols()
    
    if not symbols:
        print("❌ Chưa có dữ liệu symbols. Chạy 'python main.py init' trước!")
        return {
            'date': date,
            'symbol_count': 0,
            'total_candles': 0,
            'total_foreign': 0,
            'index_daily_count': 0,
            'error_count': 0,
            'errors': [],
            'status': 'FAILED',
        }
    
    ssi = SSIApi()
    index_codes = sync_indexes(ssi=ssi, db=db)
    sync_index_components(None, ssi=ssi, db=db)
    total_candles = 0
    total_foreign = 0
    errors = []
    for symbol in symbols:
        try:
            count = fetch_one_day_with_clients(ssi, db, symbol, date)
            total_candles += count
            foreign_record = fetch_foreign_for_symbol(ssi, symbol, date)
            if foreign_record:
                db.upsert_foreign([foreign_record])
                total_foreign += 1
        except Exception as e:
            errors.append({'symbol': symbol, 'error': str(e)})
            print(f"    ❌ {symbol}: {e}")
    
    index_count = fetch_daily_indexes(date, ssi=ssi, db=db)
    status = 'OK' if not errors else 'PARTIAL'
    print(f"\n✅ Hoàn thành ingest! Tổng số candles: {total_candles}; foreign_trading: {total_foreign}; index_daily: {index_count}; errors: {len(errors)}")
    print("ℹ️ Feature engine disabled in ingest task; no technical indicators were calculated.")
    return {
        'date': date,
        'symbol_count': len(symbols),
        'total_candles': total_candles,
        'total_foreign': total_foreign,
        'index_daily_count': index_count,
        'error_count': len(errors),
        'errors': errors,
        'status': status,
    }


# Backward-compatible alias for older imports.
daily_run = run_daily_ingest
