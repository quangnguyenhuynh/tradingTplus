from datetime import datetime, timedelta
from src.database.client import SupabaseClient
from src.pipeline.fetch_one_day import fetch_one_day
from src.engine.feature_engine import run_feature_engine

def backfill(from_date: str, to_date: str, symbols: list = None):
    """
    Lấy dữ liệu lịch sử cho nhiều ngày
    
    Args:
        from_date: YYYY-MM-DD
        to_date: YYYY-MM-DD
        symbols: Danh sách mã (None = lấy tất cả)
    """
    db = SupabaseClient()
    
    # Lấy danh sách mã nếu chưa có
    if symbols is None:
        symbols = db.get_symbols()
        if not symbols:
            print("❌ Chưa có dữ liệu symbols. Chạy 'python main.py init' trước!")
            return
    
    # Chuyển đổi ngày tháng
    start = datetime.strptime(from_date, "%Y-%m-%d")
    end = datetime.strptime(to_date, "%Y-%m-%d")
    
    total_candles = 0
    current = start
    
    print(f"🚀 Bắt đầu backfill từ {from_date} đến {to_date}")
    print(f"📊 Số lượng mã: {len(symbols)}")
    
    while current <= end:
        date_str = current.strftime("%d/%m/%Y")
        print(f"\n📅 {date_str}")
        
        for symbol in symbols:
            try:
                count = fetch_one_day(symbol, date_str)
                total_candles += count
            except Exception as e:
                print(f"    ❌ {symbol}: {e}")
        
        current += timedelta(days=1)
    
    print(f"\n🎉 Hoàn thành ingest! Tổng số candles: {total_candles}")

    print("🧮 Bắt đầu tính features sau backfill...")
    feature_count = run_feature_engine(symbols)
    print(f"✅ Hoàn thành features sau backfill: {feature_count} records")