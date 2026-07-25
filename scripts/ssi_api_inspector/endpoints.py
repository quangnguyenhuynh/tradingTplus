from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from src.config import config


@dataclass(frozen=True)
class Endpoint:
    name: str
    label: str
    method: str
    url: str
    auth_required: bool
    build_params: Callable[[Any], dict[str, Any]]
    post_json: Callable[[Any], dict[str, Any]] | None = None


def _paging(args: Any) -> dict[str, Any]:
    return {"PageIndex": args.page_index, "PageSize": args.page_size}


def _ascending(args: Any) -> dict[str, Any]:
    return {"ascending": bool(args.ascending)} if args.ascending is not None else {}


def _auth_json(_args: Any) -> dict[str, Any]:
    return {"consumerID": config.SSI_CONSUMER_ID, "consumerSecret": config.SSI_CONSUMER_SECRET}


ENDPOINTS: dict[str, Endpoint] = {
    "access-token": Endpoint("access-token", "AccessToken", "POST", config.SSI_AUTH_URL, False, lambda a: {}, _auth_json),
    "securities": Endpoint("securities", "Securities", "GET", config.SSI_SECURITIES_URL, True, lambda a: {"Market": a.market, **_paging(a)}),
    "securities-details": Endpoint("securities-details", "SecuritiesDetails", "GET", config.SSI_SECURITIES_DETAILS_URL, True, lambda a: {"Market": a.market, "Symbol": a.symbol, **_paging(a)}),
    "index-components": Endpoint("index-components", "IndexComponents", "GET", config.SSI_INDEX_COMPONENTS_URL, True, lambda a: {"IndexCode": a.index_code, **_paging(a)}),
    "index-list": Endpoint("index-list", "IndexList", "GET", config.SSI_INDEX_LIST_URL, True, lambda a: {"Exchange": a.exchange, **_paging(a)}),
    "daily-ohlc": Endpoint("daily-ohlc", "DailyOhlc", "GET", config.SSI_DAILY_OHLC_URL, True, lambda a: {"Symbol": a.symbol, "FromDate": a.date, "ToDate": a.date, **_paging(a), **_ascending(a)}),
    "intraday-ohlc": Endpoint("intraday-ohlc", "IntradayOhlc", "GET", config.SSI_INTRADAY_OHLC_URL, True, lambda a: {"Symbol": a.symbol, "FromDate": a.date, "ToDate": a.date, **_paging(a), "resolution": 1, **_ascending(a)}),
    "daily-index": Endpoint("daily-index", "DailyIndex", "GET", config.SSI_DAILY_INDEX_URL, True, lambda a: {"IndexId": a.index_code, "FromDate": a.date, "ToDate": a.date, **_paging(a)}),
    "daily-stock-price": Endpoint("daily-stock-price", "DailyStockPrice", "GET", config.SSI_DAILY_STOCK_PRICE_URL, True, lambda a: {"Symbol": a.symbol, "FromDate": a.date, "ToDate": a.date, **_paging(a), "Market": a.market}),
}

RUN_ALL_ORDER = [name for name in ENDPOINTS if name != "access-token"]
