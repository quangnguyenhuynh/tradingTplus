from datetime import datetime, timedelta, timezone
from src.database.client import SupabaseClient
from src.ssi.api import SSIApi
from src.pipeline.fetch_one_day import fetch_one_day_with_clients
from src.engine.feature_engine import run_feature_engine

VN_TZ = timezone(timedelta(hours=7))


def daily_run(date: str = None):
    """
    Lấy dữ liệu cho 1 ngày (mặc định là hôm qua)
    
    Args:
        date: DD/MM/YYYY (None = hôm qua)
    """
    if date is None:
        date = (datetime.now(VN_TZ) - timedelta(days=1)).strftime("%d/%m/%Y")
    
    print(f"📆 Daily fetch: {date}")
    
    db = SupabaseClient()
    symbols = db.get_symbols()
    
    if not symbols:
        print("❌ Chưa có dữ liệu symbols. Chạy 'python main.py init' trước!")
        return
    
    ssi = SSIApi()
    total_candles = 0
    for symbol in symbols:
        try:
            count = fetch_one_day_with_clients(ssi, db, symbol, date)
            total_candles += count
        except Exception as e:
            print(f"    ❌ {symbol}: {e}")
    
    print(f"\n✅ Hoàn thành ingest! Tổng số candles: {total_candles}")

    print("🧮 Bắt đầu tính features sau daily...")
    feature_count = run_feature_engine(symbols)
    print(f"✅ Hoàn thành features sau daily: {feature_count} records")
