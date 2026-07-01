import time
from typing import Any

import requests

from src.config import config


class SSIApi:
    def __init__(self) -> None:
        self.token: str | None = None
        self._login()

    def _login(self) -> None:
        url = config.SSI_AUTH_URL
        payload = {
            "consumerID": config.SSI_CONSUMER_ID,
            "consumerSecret": config.SSI_CONSUMER_SECRET,
        }

        print("🔐 Đang đăng nhập SSI...")

        try:
            resp = requests.post(url, json=payload, timeout=30)
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

        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    def _get_with_retry(
        self,
        url: str,
        params: dict[str, Any],
        timeout: int = 30,
    ) -> requests.Response:
        resp = requests.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=timeout,
        )

        if resp.status_code == 401:
            print("🔄 SSI token hết hạn, đang đăng nhập lại...")
            self._login()

            resp = requests.get(
                url,
                headers=self._headers(),
                params=params,
                timeout=timeout,
            )

        resp.raise_for_status()
        return resp

    def _extract_items(self, data: dict[str, Any]) -> list[dict]:
        if "dataList" in data:
            return data.get("dataList") or []

        if "data" in data:
            return data.get("data") or []

        return []

    def get_symbols(self) -> list[dict]:
        url = config.SSI_SECURITIES_URL
        all_symbols: list[dict] = []
        markets = ["HNX", "HOSE", "UPCOM", "DER"]

        print("📋 Đang lấy danh sách mã từ SSI...")

        for idx, market in enumerate(markets):
            print(f"\nLần lặp {idx + 1}: market={market}")

            try:
                time.sleep(2)

                params = {
                    "market": market,
                    "pageSize": 1000,
                }

                print(f"       -> Đang gọi API với params={params}")

                resp = self._get_with_retry(url, params)
                data = resp.json()
                symbols = self._extract_items(data)

                if symbols:
                    all_symbols.extend(symbols)
                    print(f"   ✅ {market}: {len(symbols)} symbols")
                else:
                    print(f"   ⚪ {market}: 0 symbols")

            except requests.HTTPError as e:
                status_code = e.response.status_code if e.response else "unknown"
                print(f"   ⚠️ {market}: HTTP lỗi {status_code}")

            except requests.RequestException as e:
                print(f"   ❌ {market}: lỗi kết nối SSI: {e}")

            except ValueError as e:
                print(f"   ❌ {market}: JSON không hợp lệ: {e}")

        print(f"✅ Tổng cộng: {len(all_symbols)} symbols")
        return all_symbols

    def get_daily_price(self, symbol: str, date: str) -> dict | None:
        url = config.SSI_DAILY_STOCK_PRICE_URL
        params = {
            "Symbol": symbol,
            "FromDate": date,
            "ToDate": date,
        }

        try:
            resp = self._get_with_retry(url, params)

            if not resp.text:
                return None

            data = resp.json()
            items = self._extract_items(data)

            return items[0] if items else None

        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response else "unknown"
            print(f"⚠️ Lỗi HTTP daily price {symbol}: {status_code}")
            return None

        except requests.RequestException as e:
            print(f"⚠️ Lỗi kết nối daily price {symbol}: {e}")
            return None

        except ValueError as e:
            print(f"⚠️ JSON daily price không hợp lệ {symbol}: {e}")
            return None

    def get_intraday(self, symbol: str, date: str) -> list[dict]:
        url = config.SSI_INTRADAY_OHLC_URL
        params = {
            "Symbol": symbol,
            "FromDate": date,
            "ToDate": date,
            "resolution": "1",
            "pageSize": 1000,
        }

        try:
            resp = self._get_with_retry(url, params)

            if not resp.text:
                return []

            data = resp.json()
            return self._extract_items(data)

        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response else "unknown"
            print(f"⚠️ Lỗi HTTP intraday {symbol}: {status_code}")
            return []

        except requests.RequestException as e:
            print(f"⚠️ Lỗi kết nối intraday {symbol}: {e}")
            return []

        except ValueError as e:
            print(f"⚠️ JSON intraday không hợp lệ {symbol}: {e}")
            return []