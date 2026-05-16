from datetime import datetime, timedelta
from src.database.client import SupabaseClient
from src.pipeline.fetch_one_day import fetch_one_day

def daily_run(date: str = None):
    """
    Lấy dữ liệu cho 1 ngày (mặc định là hôm qua)
    
    Args:
        date: DD/MM/YYYY (None = hôm qua)
    """
    if date is None:
        date = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
    
    print(f"📆 Daily fetch: {date}")
    
    db = SupabaseClient()
    symbols = db.get_symbols()
    
    if not symbols:
        print("❌ Chưa có dữ liệu symbols. Chạy 'python main.py init' trước!")
        return
    
    total_candles = 0
    for symbol in symbols:
        try:
            count = fetch_one_day(symbol, date)
            total_candles += count
        except Exception as e:
            print(f"    ❌ {symbol}: {e}")
    
    print(f"\n✅ Hoàn thành! Tổng số candles: {total_candles}")