from datetime import datetime, timedelta
from src.database.client import SupabaseClient
from src.ssi.api import SSIApi
from src.pipeline.fetch_one_day import fetch_one_day_with_clients
from src.pipeline.date_utils import parse_iso_date, validate_not_future

def backfill(from_date: str, to_date: str, symbols: list = None, allow_future: bool = False):
    """
    Lấy dữ liệu lịch sử cho nhiều ngày
    
    Args:
        from_date: YYYY-MM-DD
        to_date: YYYY-MM-DD
        symbols: Danh sách mã (None = lấy tất cả)
        allow_future: Cho phép future dates (mặc định False)
    """
    db = SupabaseClient()
    
    # Lấy danh sách mã nếu chưa có
    if symbols is None:
        symbols = db.get_symbols()
        if not symbols:
            print("❌ Chưa có dữ liệu symbols. Chạy 'python main.py init' trước!")
            return
    
    # Chuyển đổi ngày tháng và chặn future-date backfill ngoài ý muốn.
    start_validated = parse_iso_date(from_date)
    end_validated = parse_iso_date(to_date)
    if not allow_future:
        validate_not_future(start_validated)
        validate_not_future(end_validated)
    if start_validated.date > end_validated.date:
        raise ValueError("from_date must be <= to_date")
    start = datetime.combine(start_validated.date, datetime.min.time())
    end = datetime.combine(end_validated.date, datetime.min.time())
    
    ssi = SSIApi()
    total_candles = 0
    current = start
    
    print(f"🚀 Bắt đầu backfill từ {from_date} đến {to_date}")
    print(f"📊 Số lượng mã: {len(symbols)}")
    
    while current <= end:
        date_str = current.strftime("%d/%m/%Y")
        if current.weekday() >= 5:
            print(f"\n📅 {date_str} - bỏ qua weekend")
            current += timedelta(days=1)
            continue
        print(f"\n📅 {date_str}")
        
        for symbol in symbols:
            try:
                count = fetch_one_day_with_clients(ssi, db, symbol, date_str)
                total_candles += count
            except Exception as e:
                print(f"    ❌ {symbol}: {e}")
        
        current += timedelta(days=1)
    
    print(f"\n🎉 Hoàn thành ingest! Tổng số candles: {total_candles}")

    print("ℹ️ Feature engine disabled in ingest task; no technical indicators were calculated.")
