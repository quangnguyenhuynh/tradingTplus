import time
from typing import Any

import requests

from src.config import config


class SSIApi:
    def __init__(self) -> None:
        self.token: str | None = None
        self._login()

    def _login(self) -> None:
        payload = {"consumerID": config.SSI_CONSUMER_ID, "consumerSecret": config.SSI_CONSUMER_SECRET}
        print("🔐 Đang đăng nhập SSI...")
        try:
            resp = requests.post(config.SSI_AUTH_URL, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            print(f"❌ Lỗi kết nối khi đăng nhập SSI: {e}")
            raise
        except ValueError as e:
            print(f"❌ SSI trả JSON không hợp lệ khi đăng nhập: {e}")
            raise
        token = data.get("data", {}).get("accessToken")
        if not token:
            print(f"❌ Response không có accessToken: {data}")
            raise RuntimeError("Không tìm thấy accessToken")
        self.token = token
        print("✅ Đã đăng nhập SSI thành công")

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("SSI token chưa được khởi tạo")
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

    def _get_with_retry(self, url: str, params: dict[str, Any], timeout: int = 30) -> requests.Response:
        resp = requests.get(url, headers=self._headers(), params=params, timeout=timeout)
        if resp.status_code == 401:
            print("🔄 SSI token hết hạn, đang đăng nhập lại...")
            self._login()
            resp = requests.get(url, headers=self._headers(), params=params, timeout=timeout)
        resp.raise_for_status()
        return resp

    def _extract_items(self, data: dict[str, Any]) -> list[dict]:
        if isinstance(data.get("dataList"), list):
            return data.get("dataList") or []
        if isinstance(data.get("data"), list):
            return data.get("data") or []
        if isinstance(data.get("items"), list):
            return data.get("items") or []
        return []

    def _extract_total_record(self, data: dict[str, Any]) -> int | None:
        for key in ("totalRecord", "totalRecords", "total", "TotalRecord"):
            value = data.get(key)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None
        return None

    def _get_all_pages(self, url: str, params: dict[str, Any] | None = None, page_size: int = 1000, sleep_sec: float = 0.1) -> list[dict]:
        base_params = dict(params or {})
        all_items: list[dict] = []
        page_index = int(base_params.pop("pageIndex", 1) or 1)
        page_size = int(base_params.pop("pageSize", page_size) or page_size)
        total_record: int | None = None
        while True:
            page_params = {**base_params, "pageIndex": page_index, "pageSize": page_size}
            resp = self._get_with_retry(url, page_params)
            data = resp.json() if resp.text else {}
            items = self._extract_items(data)
            if total_record is None:
                total_record = self._extract_total_record(data)
            if not items:
                break
            all_items.extend(items)
            if total_record is not None and len(all_items) >= total_record:
                break
            if len(items) < page_size:
                break
            page_index += 1
            time.sleep(sleep_sec)
        return all_items

    def get_symbols(self) -> list[dict]:
        all_symbols: list[dict] = []
        markets = ["HNX", "HOSE", "UPCOM", "DER"]
        print("📋 Đang lấy danh sách mã từ SSI...")
        for market in markets:
            try:
                symbols = self._get_all_pages(config.SSI_SECURITIES_URL, {"market": market}, page_size=1000)
                all_symbols.extend(symbols)
                print(f"   ✅ {market}: {len(symbols)} symbols")
            except (requests.RequestException, ValueError) as e:
                print(f"   ⚠️ {market}: {e}")
        print(f"✅ Tổng cộng: {len(all_symbols)} symbols")
        return all_symbols

    def get_security_details(self, market: str | None = None, symbol: str | None = None) -> list[dict]:
        params: dict[str, Any] = {}
        if market:
            params["market"] = market
        if symbol:
            params["symbol"] = symbol
        try:
            return self._get_all_pages(config.SSI_SECURITIES_DETAILS_URL, params, page_size=1000)
        except (requests.RequestException, ValueError) as e:
            print(f"⚠️ Lỗi SecuritiesDetails: {e}")
            return []

    def get_index_list(self, exchange: str | None = None) -> list[dict]:
        params = {"exchange": exchange} if exchange else {}
        try:
            return self._get_all_pages(config.SSI_INDEX_LIST_URL, params, page_size=1000)
        except (requests.RequestException, ValueError) as e:
            print(f"⚠️ Lỗi IndexList: {e}")
            return []

    def get_index_components(self, index_code: str) -> list[dict]:
        try:
            return self._get_all_pages(config.SSI_INDEX_COMPONENTS_URL, {"IndexCode": index_code}, page_size=1000)
        except (requests.RequestException, ValueError) as e:
            print(f"⚠️ Lỗi IndexComponents {index_code}: {e}")
            return []

    def get_daily_index_raw(self, index_code: str, date: str) -> dict | None:
        params = {"IndexCode": index_code, "FromDate": date, "ToDate": date, "pageIndex": 1, "pageSize": 1000}
        try:
            resp = self._get_with_retry(config.SSI_DAILY_INDEX_URL, params)
            return resp.json() if resp.text else {}
        except (requests.RequestException, ValueError) as e:
            print(f"⚠️ Lỗi DailyIndex raw {index_code}: {e}")
            return None

    def get_daily_index(self, index_code: str, date: str) -> dict | None:
        raw = self.get_daily_index_raw(index_code, date)
        if raw is None:
            return None
        items = self._extract_items(raw)
        return items[0] if items else None

    def get_daily_price(self, symbol: str, date: str) -> dict | None:
        try:
            items = self._get_all_pages(config.SSI_DAILY_STOCK_PRICE_URL, {"Symbol": symbol, "FromDate": date, "ToDate": date}, page_size=1000)
            return items[0] if items else None
        except (requests.RequestException, ValueError) as e:
            print(f"⚠️ Lỗi daily price {symbol}: {e}")
            return None

    def get_daily_prices_for_date(self, date: str, market: str | None = None) -> list[dict]:
        params: dict[str, Any] = {"FromDate": date, "ToDate": date}
        if market:
            params["Market"] = market
        try:
            return self._get_all_pages(config.SSI_DAILY_STOCK_PRICE_URL, params, page_size=1000)
        except (requests.RequestException, ValueError) as e:
            print(f"⚠️ Lỗi daily prices date={date}: {e}")
            return []

    def get_intraday(self, symbol: str, date: str) -> list[dict]:
        params = {"Symbol": symbol, "FromDate": date, "ToDate": date, "resolution": "1"}
        try:
            return self._get_all_pages(config.SSI_INTRADAY_OHLC_URL, params, page_size=1000)
        except (requests.RequestException, ValueError) as e:
            print(f"⚠️ Lỗi intraday {symbol}: {e}")
            return []
