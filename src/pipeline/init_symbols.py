from src.ssi.api import SSIApi
from src.database.client import SupabaseClient

def init_symbols():
    print("📋 Đang lấy danh sách mã từ SSI...")
    
    ssi = SSIApi()
    db = SupabaseClient()
    
    data = ssi.get_symbols()
    
    symbols = []
    for item in data:
        symbols.append({
            'symbol': item['Symbol'],
            'market': item['Market'],
            'name': item.get('StockName', '')
        })
    
    db.upsert_symbols(symbols)
    print(f"✅ Đã lưu {len(symbols)} mã vào database")