import requests
import time
from src.config import config

class SSIApi:
    def __init__(self):
        self.token = None
        self._login()
    
    def _login(self):
        url = config.SSI_AUTH_URL
        payload = {
            'consumerID': config.SSI_CONSUMER_ID,
            'consumerSecret': config.SSI_CONSUMER_SECRET
        }
        
        print(f"🔐 Đang đăng nhập SSI...")
        
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            
            data = resp.json()
            
            if 'data' in data and 'accessToken' in data['data']:
                self.token = data['data']['accessToken']
                print("✅ Đã đăng nhập SSI thành công")
            else:
                print(f"❌ Response không có accessToken: {data}")
                raise Exception("Không tìm thấy accessToken")
            
        except Exception as e:
            print(f"❌ Lỗi đăng nhập: {e}")
            raise
    
    def _headers(self):
        return {
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/json'
        }
    
    # ✅ SỬA: Lấy symbols theo từng market riêng
    def get_symbols(self):
        url = config.SSI_SECURITIES_URL
        all_symbols = []
        
        # Các market cần lấy (gọi riêng từng cái)
        markets = ['HNX', 'HOSE', 'UPCOM', 'DER']
        
        print("📋 Đang lấy danh sách mã từ SSI...")
        
        for idx, market in enumerate(markets):
            print(f"\n lan lap {idx+1}:market={market}")
            try:
                time.sleep(2)
                self._login()
                params = {
                    'market': market,
                    'pageSize': 1000
                }
                print(f"       -> dang goi API voi params={params} ")
                resp = requests.get(
                    url, 
                    headers=self._headers(), 
                    params=params,
                    timeout=30
                )
                print(f"    -> status code:{resp.status_code}")
                if resp.status_code != 200:
                    print(f"   ⚠️ {market}: lỗi {resp.status_code}")
                    continue
                
                data = resp.json()
                symbols = data.get('data', [])
                
                if symbols:
                    all_symbols.extend(symbols)
                    print(f"   ✅ {market}: {len(symbols)} symbols")
                else:
                    print(f"   ⚪ {market}: 0 symbols")
                    
            except Exception as e:
                print(f"   ❌ {market}: {e}")
        
        print(f"✅ Tổng cộng: {len(all_symbols)} symbols")
        return all_symbols
    


    # mục 4.9 trong tài liệu SSI
    def get_daily_price(self, symbol, date):
        url = config.SSI_DAILY_STOCK_PRICE_URL
        params = {'Symbol': symbol, 'FromDate': date, 'ToDate': date}
        
        try:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
            resp.raise_for_status()
            
            if not resp.text:
                return None
            
            data = resp.json()

            if 'dataList' in data:
                items = data.get('dataList', [])
                #print(f"du lieu item 0 datalist là{items[0]}")

                return items[0] if items else None
            elif 'data' in data:
                items = data.get('data', [])
                #print(f"du lieu item 0 data là{items[0]}")
                return items[0] if items else None
            return None

        except Exception as e:
            print(f"⚠️ Lỗi daily price {symbol}: {e}")
            return None
    


    # mục 4.7 trong tài liệu SSI API
    def get_intraday(self, symbol, date):
        url = config.SSI_INTRADAY_OHLC_URL
        params = {
            'Symbol': symbol,
            'FromDate': date,
            'ToDate': date,
            'resolution': '1',
            'pageSize': 1000
        }
        
        try:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
            resp.raise_for_status()
            
            if not resp.text:
                return []
            
            data = resp.json()
            if 'dataList' in data:
                return data.get('dataList', [])
            elif 'data' in data:
                return data.get('data', [])
            return []
        except Exception as e:
            print(f"⚠️ Lỗi intraday {symbol}: {e}")
            return []