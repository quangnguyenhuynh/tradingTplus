from datetime import datetime, timedelta, timezone
from src.database.client import SupabaseClient
from src.pipeline.fetch_one_day import fetch_one_day
from src.engine.feature_engine import run_feature_engine
from src.engine.data_quality import check_data_quality

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
    
    total_candles = 0
    for symbol in symbols:
        try:
            count = fetch_one_day(symbol, date)
            total_candles += count
        except Exception as e:
            print(f"    ❌ {symbol}: {e}")
    
    print(f"\n✅ Hoàn thành ingest! Tổng số candles: {total_candles}")

    print("🧮 Bắt đầu tính features sau daily...")
    feature_count = run_feature_engine(symbols)
    print(f"✅ Hoàn thành features sau daily: {feature_count} records")

    print("🧪 Chạy data quality checks...")
    for symbol in symbols:
        check_data_quality(symbol=symbol, trading_date=datetime.strptime(date, "%d/%m/%Y").strftime("%Y-%m-%d"))
    print("✅ Data quality checks xong")