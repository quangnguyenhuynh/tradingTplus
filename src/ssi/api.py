import logging
import time
from typing import Any

import requests

from src.config import config

logger = logging.getLogger(__name__)

DAILY_STOCK_PRICE_PAGE_SIZE = 100
SSI_MAX_ATTEMPTS = 3
SSI_RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}


class SSIResponseError(RuntimeError):
    """SSI returned a response that cannot be treated as successful market data."""


class SSIEmptyResponseError(SSIResponseError):
    """SSI reported records but returned an empty first page after bounded retries."""


class SSIDataMismatchError(SSIResponseError):
    """SSI returned data, but none matched the requested symbol/date."""


def _get_case_insensitive(data: dict[str, Any], *keys: str) -> Any:
    lower = {str(k).lower(): v for k, v in (data or {}).items()}
    for key in keys:
        if key in data:
            return data.get(key)
        if key.lower() in lower:
            return lower[key.lower()]
    return None

def _parse_ssi_payload_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            from datetime import datetime
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            pass
    return None


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
        reauthenticated = False
        for attempt in range(1, SSI_MAX_ATTEMPTS + 1):
            try:
                resp = requests.get(url, headers=self._headers(), params=params, timeout=timeout)
            except requests.RequestException as exc:
                if attempt >= SSI_MAX_ATTEMPTS:
                    raise SSIResponseError(
                        f"SSI network request failed after {SSI_MAX_ATTEMPTS} attempts: endpoint={url}"
                    ) from exc
                sleep_sec = 0.5 * (2 ** (attempt - 1))
                logger.warning(
                    "SSI request retry %s/%s after network error: endpoint=%s page=%s",
                    attempt,
                    SSI_MAX_ATTEMPTS,
                    url,
                    params.get("pageIndex"),
                )
                time.sleep(sleep_sec)
                continue

            if resp.status_code == 401 and not reauthenticated:
                logger.warning("SSI token expired; reauthenticating once: endpoint=%s", url)
                self._login()
                reauthenticated = True
                try:
                    resp = requests.get(
                        url,
                        headers=self._headers(),
                        params=params,
                        timeout=timeout,
                    )
                except requests.RequestException as exc:
                    if attempt >= SSI_MAX_ATTEMPTS:
                        raise SSIResponseError(
                            "SSI network request failed after token refresh: "
                            f"endpoint={url}"
                        ) from exc
                    continue

            if resp.status_code in SSI_RETRYABLE_HTTP_STATUSES and attempt < SSI_MAX_ATTEMPTS:
                sleep_sec = 0.5 * (2 ** (attempt - 1))
                logger.warning(
                    "SSI HTTP retry %s/%s: endpoint=%s status=%s page=%s",
                    attempt,
                    SSI_MAX_ATTEMPTS,
                    url,
                    resp.status_code,
                    params.get("pageIndex"),
                )
                time.sleep(sleep_sec)
                continue

            try:
                resp.raise_for_status()
            except requests.RequestException as exc:
                raise SSIResponseError(
                    f"SSI HTTP error status={resp.status_code}: endpoint={url}"
                ) from exc
            return resp

        raise SSIResponseError(f"SSI request exhausted retries: endpoint={url}")

    def _extract_items(self, data: dict[str, Any]) -> list[dict]:
        if isinstance(data.get("dataList"), list):
            return data.get("dataList") or []
        if isinstance(data.get("data"), list):
            return data.get("data") or []
        if isinstance(data.get("items"), list):
            return data.get("items") or []
        return []

    def _extract_total_record(self, data: dict[str, Any]) -> int | None:
        lower = {str(key).lower(): value for key, value in data.items()}
        for key in ("totalrecord", "totalrecords", "total"):
            value = lower.get(key)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None
        return None

    def _validate_response_envelope(self, data: dict[str, Any], url: str) -> None:
        status = _get_case_insensitive(data, "status")
        if status is not None and str(status).strip().upper() not in {"SUCCESS", "OK"}:
            message = _get_case_insensitive(data, "message")
            raise SSIResponseError(
                f"SSI response status={status!r} message={message!r}: endpoint={url}"
            )

    def _get_all_pages(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        page_size: int = 1000,
        sleep_sec: float = 0.1,
        empty_first_page_attempts: int = SSI_MAX_ATTEMPTS,
    ) -> list[dict]:
        base_params = dict(params or {})
        all_items: list[dict] = []
        page_index = int(base_params.pop("pageIndex", 1) or 1)
        page_size = int(base_params.pop("pageSize", page_size) or page_size)
        total_record: int | None = None
        while True:
            page_params = {**base_params, "pageIndex": page_index, "pageSize": page_size}
            data: dict[str, Any] = {}
            items: list[dict] = []
            page_total: int | None = None
            page_attempts = empty_first_page_attempts if page_index == 1 else 1
            for page_attempt in range(1, page_attempts + 1):
                resp = self._get_with_retry(url, page_params)
                data = resp.json() if resp.text else {}
                if not isinstance(data, dict):
                    raise SSIResponseError(
                        f"SSI response must be a JSON object: endpoint={url}"
                    )
                self._validate_response_envelope(data, url)
                items = self._extract_items(data)
                page_total = self._extract_total_record(data)
                if items or page_total == 0 or page_attempt >= page_attempts:
                    break
                logger.warning(
                    "SSI empty first-page retry %s/%s: endpoint=%s page_size=%s total_record=%s",
                    page_attempt,
                    page_attempts,
                    url,
                    page_size,
                    page_total,
                )
                time.sleep(0.5 * (2 ** (page_attempt - 1)))

            if not items and page_total is not None and page_total > len(all_items):
                raise SSIEmptyResponseError(
                    "SSI returned an empty page before totalRecord was reached: "
                    f"endpoint={url} page={page_index} total_record={page_total}"
                )
            if total_record is None:
                total_record = page_total
            if not items:
                break
            all_items.extend(items)
            if total_record is not None and len(all_items) >= total_record:
                break
            if total_record is None and len(items) < page_size:
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
            except (SSIResponseError, requests.RequestException, ValueError) as e:
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
        except (SSIResponseError, requests.RequestException, ValueError) as e:
            print(f"⚠️ Lỗi SecuritiesDetails: {e}")
            return []

    def get_index_list(self, exchange: str | None = None) -> list[dict]:
        params = {"exchange": exchange} if exchange else {}
        try:
            return self._get_all_pages(config.SSI_INDEX_LIST_URL, params, page_size=1000)
        except (SSIResponseError, requests.RequestException, ValueError) as e:
            print(f"⚠️ Lỗi IndexList: {e}")
            return []

    def get_index_components(self, index_code: str) -> list[dict]:
        try:
            return self._get_all_pages(config.SSI_INDEX_COMPONENTS_URL, {"IndexCode": index_code}, page_size=1000)
        except (SSIResponseError, requests.RequestException, ValueError) as e:
            print(f"⚠️ Lỗi IndexComponents {index_code}: {e}")
            return []

    def get_daily_index_raw(self, index_code: str, date: str) -> dict | None:
        params = {"IndexCode": index_code, "FromDate": date, "ToDate": date, "pageIndex": 1, "pageSize": 1000}
        try:
            resp = self._get_with_retry(config.SSI_DAILY_INDEX_URL, params)
            return resp.json() if resp.text else {}
        except (SSIResponseError, requests.RequestException, ValueError) as e:
            print(f"⚠️ Lỗi DailyIndex raw {index_code}: {e}")
            return None

    def get_daily_index(self, index_code: str, date: str) -> dict | None:
        raw = self.get_daily_index_raw(index_code, date)
        if raw is None:
            return None
        items = self._extract_items(raw)
        return items[0] if items else None

    def get_daily_price_items(self, symbol: str, date: str) -> list[dict]:
        return self._get_all_pages(
            config.SSI_DAILY_STOCK_PRICE_URL,
            {"Symbol": symbol, "FromDate": date, "ToDate": date},
            page_size=DAILY_STOCK_PRICE_PAGE_SIZE,
        )

    def get_daily_price(self, symbol: str, date: str) -> dict | None:
        from src.pipeline.date_utils import parse_ddmmyyyy
        requested_iso = parse_ddmmyyyy(date).iso
        requested_symbol = symbol.upper()
        items = self.get_daily_price_items(symbol, date)
        for item in items:
            item_symbol = _get_case_insensitive(item, "Symbol", "symbol", "Ticker", "StockSymbol")
            item_date = _parse_ssi_payload_date(_get_case_insensitive(item, "TradingDate", "tradingDate", "Date", "date", "TradingTime"))
            if str(item_symbol or "").upper() == requested_symbol and item_date == requested_iso:
                return item
        if items:
            raise SSIDataMismatchError(
                f"SSI daily price returned no matching item for symbol={symbol} date={date}"
            )
        return None

    def get_daily_prices_for_date(self, date: str, market: str | None = None) -> list[dict]:
        params: dict[str, Any] = {"FromDate": date, "ToDate": date}
        if market:
            params["Market"] = market
        return self._get_all_pages(
            config.SSI_DAILY_STOCK_PRICE_URL,
            params,
            page_size=DAILY_STOCK_PRICE_PAGE_SIZE,
        )


    def get_foreign_trading(self, symbol: str | None = None, date: str | None = None, market: str | None = None) -> list[dict]:
        """Return foreign trading fields from official DailyStockPrice data.

        SSI FastConnect Data REST docs do not list a standalone ForeignTrading endpoint.
        DailyStockPrice contains the foreign buy/sell/net/room fields, so this method
        intentionally derives foreign rows from the official DailyStockPrice endpoint.
        """
        if not date:
            print("⚠️ Foreign trading requires date because it is derived from DailyStockPrice")
            return []
        if symbol:
            item = self.get_daily_price(symbol, date)
            return [item] if item else []
        return self.get_daily_prices_for_date(date, market=market)

    def get_orderbook_snapshot(self, symbol: str) -> dict | None:
        """Fetch orderbook from an optional/private endpoint if configured.

        The public FastConnect Data REST spec lists Securities, SecuritiesDetails,
        IndexComponents, IndexList, DailyOhlc, IntradayOhlc, DailyIndex, and
        DailyStockPrice. It does not list a REST orderbook endpoint, so by default
        this returns None and lets the pipeline log unsupported/missing endpoint.
        """
        if not config.SSI_ORDERBOOK_URL:
            print("⚠️ Orderbook unsupported/missing endpoint: SSI_ORDERBOOK_URL is not configured in official REST docs")
            return None
        params = {"Symbol": symbol}
        try:
            items = self._get_all_pages(config.SSI_ORDERBOOK_URL, params, page_size=1000)
            if items:
                return items[0] if len(items) == 1 else {"Symbol": symbol, "dataList": items}
            return None
        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response else "unknown"
            if status_code in (400, 404):
                print(f"⚠️ Orderbook unsupported/missing endpoint for {symbol}: HTTP {status_code}")
                return None
            print(f"⚠️ Lỗi HTTP Orderbook {symbol}: {status_code}")
            return None
        except (SSIResponseError, requests.RequestException, ValueError) as e:
            print(f"⚠️ Lỗi Orderbook {symbol}: {e}")
            return None

    def get_intraday(self, symbol: str, date: str) -> list[dict]:
        params = {"Symbol": symbol, "FromDate": date, "ToDate": date, "resolution": "1"}
        return self._get_all_pages(config.SSI_INTRADAY_OHLC_URL, params, page_size=1000)
