#!/usr/bin/env python3
import requests
import os
from dotenv import load_dotenv

load_dotenv()

def test_connection():
    print("=" * 50)
    print("TEST KẾT NỐI SSI API")
    print("=" * 50)
    
    consumer_id = os.getenv('SSI_CONSUMER_ID')
    consumer_secret = os.getenv('SSI_CONSUMER_SECRET')
    
    # URL mới theo tài liệu SSI
    url = 'https://fc-data.ssi.com.vn/api/v2/Market/AccessToken'
    
    print(f"\n1. URL: {url}")
    print(f"2. Consumer ID: {consumer_id[:10] if consumer_id else 'None'}...")
    
    if not consumer_id or not consumer_secret:
        print("   ❌ Thiếu credentials")
        return
    
    print("\n3. Đang gọi API...")
    
    try:
        resp = requests.post(url, json={
            'consumerID': consumer_id,
            'consumerSecret': consumer_secret
        }, timeout=30)
        
        print(f"   Status code: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data and 'accessToken' in data['data']:
                print(f"   ✅ Thành công! Token: {data['data']['accessToken'][:50]}...")
            else:
                print(f"   ❌ Response: {data}")
        else:
            print(f"   ❌ Lỗi: {resp.text[:200] if resp.text else 'EMPTY'}")
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")

if __name__ == "__main__":
    test_connection()