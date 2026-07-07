from datetime import datetime, timedelta, timezone
from src.database.client import SupabaseClient
from src.ssi.api import SSIApi
from src.pipeline.fetch_one_day import fetch_one_day_with_clients
from src.pipeline.index_data import fetch_daily_indexes, sync_indexes, sync_index_components
from src.pipeline.foreign_trading import fetch_foreign_for_symbol
from src.pipeline.date_utils import latest_previous_weekday

VN_TZ = timezone(timedelta(hours=7))


def daily_run(date: str = None):
    """
    Lấy dữ liệu cho 1 ngày (mặc định là hôm qua)
    
    Args:
        date: DD/MM/YYYY (None = hôm qua)
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
        return
    
    ssi = SSIApi()
    index_codes = sync_indexes(ssi=ssi, db=db)
    sync_index_components(None, ssi=ssi, db=db)
    total_candles = 0
    total_foreign = 0
    for symbol in symbols:
        try:
            count = fetch_one_day_with_clients(ssi, db, symbol, date)
            total_candles += count
            foreign_record = fetch_foreign_for_symbol(ssi, symbol, date)
            if foreign_record:
                db.upsert_foreign([foreign_record])
                total_foreign += 1
        except Exception as e:
            print(f"    ❌ {symbol}: {e}")
    
    index_count = fetch_daily_indexes(date, ssi=ssi, db=db)
    print(f"\n✅ Hoàn thành ingest! Tổng số candles: {total_candles}; foreign_trading: {total_foreign}; index_daily: {index_count}")
    print("ℹ️ Feature engine disabled in ingest task; no technical indicators were calculated.")
