import hashlib
import json
from datetime import datetime
from src.ssi.api import SSIApi
from src.database.client import SupabaseClient

#######################
    # hàm định dạng lại timestamp cho phù hợp DB
def parse_time(date_str, time_str):
    """Chuyển DD/MM/YYYY và HH:MM:SS thành ISO format"""
    try:
        full_str = f"{date_str} {time_str}"
        dt = datetime.strptime(full_str, "%d/%m/%Y %H:%M:%S")
        return dt.isoformat()
    except Exception as e:
        print(f"   ⚠️ Lỗi parse time: {date_str} {time_str} - {e}")
            # Fallback: chỉ dùng date
        try:
            day, month, year = date_str.split('/')
            dt = datetime(int(year), int(month), int(day))
            return dt.isoformat()
        except Exception:
            return None
#########################     



def fetch_one_day(symbol: str, date: str) -> int:
    """
    Lấy dữ liệu 1 ngày cho 1 mã
    
    Args:
        symbol: Mã chứng khoán (VD: 'SSI')
        date: DD/MM/YYYY
    """
    ssi = SSIApi()
    db = SupabaseClient()
    #print(f"ngày được truyền vào {date}")

   

    # Bước 1: Lấy giá tham chiếu, trần, sàn
    daily = ssi.get_daily_price(symbol, date)
    if not daily:
        print(f"  ⚠️ {symbol}: không có dữ liệu ngày {date}")
        return 0
    #print(f"dữ liệu daily là {daily}")

    # Bước 2: Lấy dữ liệu từng phút
    candles = ssi.get_intraday(symbol, date)
    if not candles:
        print(f"  ⚠️ {symbol}: không có dữ liệu intraday")
        return 0
    #print(f"dữ liệu candles là {candles}")
    raw_records = []
    clean_records = []
    prev_volume = 0
    
    for i, c in enumerate(candles):
        time_str = c.get('Time', '')
        #print(f"lay thoi gian intraday {time_str}")
        time_iso = parse_time(date, time_str)
        if time_iso is None:
            print(f"  ⚠️ {symbol}: bỏ qua candle lỗi timestamp: {time_str}")
            continue
        #print(f"lay thoi gian time iso {time_iso}")
        
        # Tính volume_delta
        current_volume = int(c.get('Volume', 0))
        volume_delta = current_volume - prev_volume if i > 0 else 0
        prev_volume = current_volume
        #print(f"ngày ghi vô db {time_iso}")

        # === Raw data ===
        raw_records.append({
            'symbol': symbol,
            'time': time_iso,  # ✅ Dùng ISO format
            'open': float(c.get('Open', 0)),
            'high': float(c.get('High', 0)),
            'low': float(c.get('Low', 0)),
            'close': float(c.get('Close', 0)),
            'volume': current_volume,
            'data_hash': hashlib.sha256(
                json.dumps(c, sort_keys=True).encode()
            ).hexdigest()
        })
        
        # === Clean data ===
        clean_records.append({
            'symbol': symbol,
            'timeframe': '1m',
            'time': time_iso,  # ✅ Dùng ISO format
            'open': float(c.get('Open', 0)),
            'high': float(c.get('High', 0)),
            'low': float(c.get('Low', 0)),
            'close': float(c.get('Close', 0)),
            'volume': current_volume,
            'value': int(c.get('Value', 0)),
            'volume_delta': volume_delta,
            'reference_price': float(daily.get('RefPrice', 0)),
            'ceiling_price': float(daily.get('CeilingPrice', 0)),
            'floor_price': float(daily.get('FloorPrice', 0))
        })
    
    # Bước 3: Lưu vào database
    if raw_records:
        db.insert_raw(raw_records)
    
    if clean_records:
        db.upsert_intraday(clean_records)
    
    print(f"  ✅ {symbol}: {len(clean_records)} candles")
    return len(clean_records)