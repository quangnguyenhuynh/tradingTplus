# check_symbol_count.py
import requests
import os
from dotenv import load_dotenv
from src.config import config

load_dotenv()


def test_all_markets():
    # Đăng nhập
    url = config.SSI_AUTH_URL
    resp = requests.post(url, json={
        'consumerID': os.getenv('SSI_CONSUMER_ID'),
        'consumerSecret': os.getenv('SSI_CONSUMER_SECRET')
    })
    token = resp.json()['data']['accessToken']
    
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
    
    # Cách 1: Gọi không có market filter
    print("\n1. Gọi API không có market filter:")
    url = config.SSI_SECURITIES_URL
    resp = requests.get(url, headers=headers, params={'pageSize': 1000})
    data = resp.json()
    symbols = data.get('data', [])
    
    # Đếm theo market
    market_counts = {}
    for s in symbols:
        m = s.get('Market', 'Unknown')
        market_counts[m] = market_counts.get(m, 0) + 1
    
    print(f"   Tổng: {len(symbols)} symbols")
    for m, count in market_counts.items():
        print(f"   {m}: {count}")
    
    # Cách 2: Thử với tham số market khác nhau
    print("\n2. Thử với tham số market:")
    for market in ['HOSE', 'HNX', 'UPCOM', 'DERIVATIVES']:
        resp = requests.get(url, headers=headers, params={'market': market, 'pageSize': 100})
        data = resp.json()
        symbols = data.get('data', [])
        print(f"   market={market}: {len(symbols)} symbols")

if __name__ == "__main__":
    test_all_markets()