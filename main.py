#!/usr/bin/env python3
"""
Trading Pipeline - SSI to Supabase

Cách dùng:
    python main.py init          # Lấy danh sách mã (chạy 1 lần)
    python main.py backfill [from_date] [to_date]  # Mặc định: 2023-01-01 -> hôm nay
    python main.py daily         # Lấy dữ liệu hôm qua (chạy mỗi ngày)
    python main.py test          # Test thử với mã SSI
"""

import sys
from datetime import datetime, timedelta, timezone
from src.pipeline import init_symbols, backfill, daily_run, fetch_one_day

VN_TZ = timezone(timedelta(hours=7))


def _validate_date_yyyy_mm_dd(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1]
    
    if cmd == 'init':
        init_symbols()
    
    elif cmd == 'backfill':
        print("🚀 Bắt đầu backfill lịch sử...")
        from_date = sys.argv[2] if len(sys.argv) > 2 else "2023-01-01"
        to_date = sys.argv[3] if len(sys.argv) > 3 else datetime.now(VN_TZ).strftime("%Y-%m-%d")

        if not _validate_date_yyyy_mm_dd(from_date) or not _validate_date_yyyy_mm_dd(to_date):
            print("❌ Sai định dạng ngày. Dùng YYYY-MM-DD, ví dụ: python main.py backfill 2024-01-01 2024-12-31")
            return

        if from_date > to_date:
            print("❌ from_date phải nhỏ hơn hoặc bằng to_date")
            return

        backfill(from_date, to_date)
    
    elif cmd == 'daily':
        daily_run()
    
    elif cmd == 'test':
        print("🧪 Test với mã SSI...")
        yesterday = (datetime.now(VN_TZ) - timedelta(days=1)).strftime("%d/%m/%Y")
        #print(f"yesterday la {yesterday}")
        count = fetch_one_day('SSI', yesterday)
        print(f"✅ Đã lưu {count} candles cho SSI")
        print("💡 Kiểm tra database để xác nhận dữ liệu đã được lưu")
    
    else:
        print(f"❌ Không biết lệnh: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()