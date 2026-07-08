#!/usr/bin/env python3
"""
Test kết nối Supabase
Chạy: python test_supabase.py
"""

import os
import argparse
import sys
from dotenv import load_dotenv

# Load .env
load_dotenv()

def test_supabase_connection():
    print("=" * 50)
    print("TEST KẾT NỐI SUPABASE")
    print("=" * 50)
    
    # 1. Kiểm tra environment variables
    print("\n1. Kiểm tra cấu hình trong .env:")
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    supabase_service_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    print(f"   SUPABASE_URL: {supabase_url if supabase_url else '❌ MISSING'}")
    print(f"   SUPABASE_KEY: {supabase_key[:20] + '...' if supabase_key else '❌ MISSING'}")
    print(f"   SUPABASE_SERVICE_KEY: {'✅ Có' if supabase_service_key else '❌ MISSING'}")
    
    if not supabase_url or not supabase_key:
        print("\n   ❌ Thiếu SUPABASE_URL hoặc SUPABASE_KEY trong file .env")
        print("   → Vui lòng thêm vào .env:")
        print("     SUPABASE_URL=https://your-project.supabase.co")
        print("     SUPABASE_KEY=your-anon-key")
        return False
    
    # 2. Thử kết nối
    print("\n2. Đang kết nối Supabase...")
    try:
        from supabase import create_client
        
        client = create_client(supabase_url, supabase_key)
        print("   ✅ Tạo client thành công")
        
        # 3. Thử query đơn giản
        print("\n3. Thử query bảng symbols...")
        try:
            result = client.table('symbols').select('count', count='exact').limit(1).execute()
            print(f"   ✅ Query thành công! (code: {result.status_code})")
            print(f"   📊 Số lượng symbols hiện có: {result.count if result.count else 0}")
        except Exception as e:
            print(f"   ⚠️ Bảng symbols chưa có hoặc lỗi: {e}")
            print("   → Bạn cần chạy file schema.sql trong Supabase SQL Editor trước")
        
        # 4. Thử lấy danh sách bảng
        print("\n4. Kiểm tra các bảng đã tạo...")
        try:
            # Thử query từng bảng
            tables = ['symbols', 'stock_intraday', 'orderbook_snapshot', 'foreign_trading', 'features', 'backtest_data', 'raw_intraday']
            existing = []
            missing = []
            
            for table in tables:
                try:
                    result = client.table(table).select('count', count='exact').limit(1).execute()
                    existing.append(table)
                except:
                    missing.append(table)
            
            if existing:
                print(f"   ✅ Các bảng đã có: {', '.join(existing)}")
            if missing:
                print(f"   ⚠️ Các bảng chưa có: {', '.join(missing)}")
                print("   → Chạy file supabase_migrations/schema.sql trong Supabase SQL Editor")
                
        except Exception as e:
            print(f"   ⚠️ Không thể kiểm tra bảng: {e}")
        
        print("\n" + "=" * 50)
        print("✅ KẾT NỐI SUPABASE THÀNH CÔNG!")
        print("=" * 50)
        return True
        
    except ImportError as e:
        print(f"\n   ❌ Không thể import supabase: {e}")
        print("   → Chạy: pip install supabase")
        return False
    except Exception as e:
        print(f"\n   ❌ Lỗi kết nối: {e}")
        return False

def test_insert_test_data():
    """Thử insert 1 record test vào bảng symbols"""
    print("\n" + "=" * 50)
    print("TEST INSERT DỮ LIỆU")
    print("=" * 50)
    
    try:
        from supabase import create_client
        from dotenv import load_dotenv
        load_dotenv()
        
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')
        
        if not supabase_url or not supabase_key:
            print("❌ Thiếu cấu hình")
            return False
        
        client = create_client(supabase_url, supabase_key)
        
        # Thử insert 1 record test
        test_symbol = {
            'symbol': 'TEST',
            'market': 'TEST',
            'name': 'Test Symbol'
        }
        
        print("Đang insert test symbol 'TEST'...")
        result = client.table('symbols').upsert(test_symbol).execute()
        print(f"✅ Insert thành công! (code: {result.status_code})")
        
        # Xóa test record
        print("Đang xóa test symbol...")
        client.table('symbols').delete().eq('symbol', 'TEST').execute()
        print("✅ Đã xóa test symbol")
        
        return True
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read-only Supabase connection check by default.")
    parser.add_argument("--write-test", action="store_true", help="Temporarily upsert/delete symbol TEST after connection succeeds.")
    args = parser.parse_args()

    success = test_supabase_connection()
    if success and args.write_test:
        print("\n⚠️ --write-test enabled: inserting then deleting temporary symbol TEST")
        success = test_insert_test_data()
    elif success:
        print("\n✅ Read-only check completed. No test insert was attempted. Pass --write-test to exercise insert/delete.")

    sys.exit(0 if success else 1)