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
from datetime import datetime, timedelta
from src.pipeline import init_symbols, backfill, daily_run, fetch_one_day


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
        to_date = sys.argv[3] if len(sys.argv) > 3 else datetime.now().strftime("%Y-%m-%d")
        backfill(from_date, to_date)
    
    elif cmd == 'daily':
        daily_run()
    
    elif cmd == 'test':
        print("🧪 Test với mã SSI...")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
        #print(f"yesterday la {yesterday}")
        count = fetch_one_day('SSI', yesterday)
        print(f"✅ Đã lưu {count} candles cho SSI")
        print("💡 Kiểm tra database để xác nhận dữ liệu đã được lưu")
    
    else:
        print(f"❌ Không biết lệnh: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()