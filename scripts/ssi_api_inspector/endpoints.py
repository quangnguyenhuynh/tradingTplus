from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from src.config import config
from src.ssi.v3 import securities_summary_params

V3_BASE = "https://api.ssi.com.vn/api/v3"
DATA_SOURCES = ("ssi_v3", "ssi_v2")


class ParameterError(ValueError):
    """The selected endpoint cannot be called with the supplied CLI arguments."""


@dataclass(frozen=True)
class Endpoint:
    name: str
    native_name: str
    label: str
    method: str
    url: str
    auth_required: bool
    response_kind: str
    build_params: Callable[[Any], dict[str, Any]]
    post_json: Callable[[Any], dict[str, Any]] | None = None
    alias_for: str | None = None


def parse_date(value: str) -> datetime:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise ParameterError(f"Invalid date {value!r}; use DD/MM/YYYY or YYYY-MM-DD")


def _dates(args: Any, *, intraday: bool = False, single_only: bool = False) -> tuple[str, str]:
    date, start, end = args.date, args.from_date, args.to_date
    if date and (start or end):
        raise ParameterError("--date cannot be used with --from-date/--to-date")
    if bool(start) != bool(end):
        raise ParameterError("--from-date and --to-date must be supplied together")
    if single_only and (start or end):
        raise ParameterError("This endpoint accepts --date only, not a date range")
    if date:
        start_dt = end_dt = parse_date(date)
    elif start and end:
        start_dt, end_dt = parse_date(start), parse_date(end)
    else:
        raise ParameterError("This endpoint requires --date or both --from-date and --to-date")
    if start_dt > end_dt:
        raise ParameterError("--from-date must be earlier than or equal to --to-date")
    if intraday:
        return start_dt.strftime("%Y/%m/%d 00:00:00"), end_dt.strftime("%Y/%m/%d 23:59:59")
    return start_dt.strftime("%Y/%m/%d"), end_dt.strftime("%Y/%m/%d")


def _one_selector(args: Any, *names: str) -> tuple[str, str]:
    selected = [(name, getattr(args, name)) for name in names if getattr(args, name, None)]
    if len(selected) != 1:
        flags = ", ".join("--" + name.replace("_", "-") for name in names)
        raise ParameterError(f"Supply exactly one selector: {flags}")
    return selected[0]


def _paging_v3(args: Any) -> dict[str, Any]:
    return {"pageIndex": args.page_index, "pageSize": args.page_size}


def _paging_v2(args: Any) -> dict[str, Any]:
    return {"PageIndex": args.page_index, "PageSize": args.page_size}


def _v3_board(args: Any) -> dict[str, Any]:
    name, value = _one_selector(args, "symbol", "board", "index_code")
    return {"index" if name == "index_code" else name: value}


def _v3_summary(args: Any) -> dict[str, Any]:
    name, value = _one_selector(args, "symbol", "index_code")
    start, end = _dates(args)
    if name == "symbol":
        return securities_summary_params(
            value, start, end, page_index=args.page_index, page_size=args.page_size
        )
    return {"index": value, "from": start, "to": end, **_paging_v3(args)}


def _v3_index_summary(args: Any) -> dict[str, Any]:
    name, value = _one_selector(args, "board", "index_code")
    day, _ = _dates(args, single_only=True)
    return {"index" if name == "index_code" else name: value, "tradingDate": day}


def _v3_ohlc(args: Any, intraday: bool) -> dict[str, Any]:
    if not args.symbol:
        raise ParameterError("This endpoint requires --symbol")
    start, end = _dates(args, intraday=intraday)
    result = {"symbol": args.symbol, "from": start, "to": end,
              "timeFrame": "1m" if intraday else "1d", **_paging_v3(args)}
    if args.ascending is not None:
        result["ascending"] = bool(args.ascending)
    return result


def _v3_master(args: Any) -> dict[str, Any]:
    start, end = _dates(args)
    return {"from": start, "to": end, **_paging_v3(args)}


def _v3_auth(_args: Any) -> dict[str, Any]:
    return {"apiKey": config.SSI_API_KEY, "apiSecret": config.SSI_API_SECRET}


def _v2_auth(_args: Any) -> dict[str, Any]:
    return {"consumerID": config.SSI_CONSUMER_ID, "consumerSecret": config.SSI_CONSUMER_SECRET}


def _v2_dates(args: Any) -> tuple[str, str]:
    start, end = _dates(args)
    # Preserve the legacy endpoint's established DD/MM/YYYY request contract.
    return datetime.strptime(start, "%Y/%m/%d").strftime("%d/%m/%Y"), datetime.strptime(end, "%Y/%m/%d").strftime("%d/%m/%Y")


def _v2_symbol_dates(args: Any, *, market: bool = False, intraday: bool = False) -> dict[str, Any]:
    if not args.symbol:
        raise ParameterError("This endpoint requires --symbol")
    start, end = _v2_dates(args)
    result = {"Symbol": args.symbol, "FromDate": start, "ToDate": end, **_paging_v2(args)}
    if market:
        board = args.market or args.board
        if board:
            result["Market"] = board
    if intraday:
        result["resolution"] = 1
    if args.ascending is not None and not market:
        result["ascending"] = bool(args.ascending)
    return result


V3_ENDPOINTS: dict[str, Endpoint] = {
    "access-token": Endpoint("access-token", "access-token", "Auth token", "POST", f"{V3_BASE}/auth/token", False, "auth", lambda a: {}, _v3_auth),
    "securities-by-board": Endpoint("securities-by-board", "securities-by-board", "securitiesByBoard", "GET", f"{V3_BASE}/data/securitiesByBoard", True, "data", _v3_board),
    "securities-summary": Endpoint("securities-summary", "securities-summary", "securitiesSummary", "GET", f"{V3_BASE}/data/securitiesSummary", True, "data", _v3_summary),
    "index-list": Endpoint("index-list", "index-list", "indexList", "GET", f"{V3_BASE}/data/indexList", True, "data", lambda a: ({"board": a.board or a.exchange} if a.board or a.exchange else {})),
    "index-summary": Endpoint("index-summary", "index-summary", "indexSummary", "GET", f"{V3_BASE}/data/indexSummary", True, "data", _v3_index_summary),
    "daily-ohlc": Endpoint("daily-ohlc", "daily-ohlc", "OHLC (1d)", "GET", f"{V3_BASE}/data/ohlc", True, "data", lambda a: _v3_ohlc(a, False)),
    "intraday-ohlc": Endpoint("intraday-ohlc", "intraday-ohlc", "OHLC (1m)", "GET", f"{V3_BASE}/data/ohlc", True, "data", lambda a: _v3_ohlc(a, True)),
    "master-data": Endpoint("master-data", "master-data", "masterdata", "GET", f"{V3_BASE}/data/masterdata", True, "data", _v3_master),
}

# Compatibility aliases are separate lookup entries but never appear in run-all.
for alias, native in {
    "securities": "securities-by-board", "securities-details": "securities-by-board",
    "index-components": "securities-by-board", "daily-stock-price": "securities-summary",
    "daily-index": "index-summary",
}.items():
    base = V3_ENDPOINTS[native]
    if alias == "securities":
        builder = lambda a: {"board": a.board or a.market} if a.board or a.market else (_ for _ in ()).throw(ParameterError("securities requires --board or --market"))
    elif alias == "securities-details":
        builder = lambda a: {"symbol": a.symbol} if a.symbol else (_ for _ in ()).throw(ParameterError("securities-details requires --symbol"))
    elif alias == "index-components":
        builder = lambda a: {"index": a.index_code} if a.index_code else (_ for _ in ()).throw(ParameterError("index-components requires --index-code"))
    elif alias == "daily-stock-price":
        def builder(a: Any) -> dict[str, Any]:
            if not a.symbol:
                raise ParameterError("daily-stock-price requires --symbol")
            params = _v3_summary(a)
            if "index" in params:
                raise ParameterError("daily-stock-price requires --symbol")
            return params
    else:
        builder = lambda a: ({"index": a.index_code, "tradingDate": _dates(a, single_only=True)[0]} if a.index_code else (_ for _ in ()).throw(ParameterError("daily-index requires --index-code")))
    V3_ENDPOINTS[alias] = Endpoint(alias, native, base.label, base.method, base.url, base.auth_required,
                                   base.response_kind, builder, base.post_json, native)

V2_ENDPOINTS: dict[str, Endpoint] = {
    "access-token": Endpoint("access-token", "access-token", "AccessToken (legacy v2)", "POST", config.SSI_AUTH_URL, False, "auth", lambda a: {}, _v2_auth),
    "securities": Endpoint("securities", "securities", "Securities (legacy v2)", "GET", config.SSI_SECURITIES_URL, True, "data", lambda a: {"Market": a.market or a.board, **_paging_v2(a)} if a.market or a.board else (_ for _ in ()).throw(ParameterError("securities requires --market or --board"))),
    "securities-details": Endpoint("securities-details", "securities-details", "SecuritiesDetails (legacy v2)", "GET", config.SSI_SECURITIES_DETAILS_URL, True, "data", lambda a: {"Market": a.market or a.board, "Symbol": a.symbol, **_paging_v2(a)} if (a.market or a.board) and a.symbol else (_ for _ in ()).throw(ParameterError("securities-details requires --symbol and --market/--board"))),
    "index-components": Endpoint("index-components", "index-components", "IndexComponents (legacy v2)", "GET", config.SSI_INDEX_COMPONENTS_URL, True, "data", lambda a: {"IndexCode": a.index_code, **_paging_v2(a)} if a.index_code else (_ for _ in ()).throw(ParameterError("index-components requires --index-code"))),
    "index-list": Endpoint("index-list", "index-list", "IndexList (legacy v2)", "GET", config.SSI_INDEX_LIST_URL, True, "data", lambda a: {"Exchange": a.exchange or a.board, **_paging_v2(a)} if a.exchange or a.board else _paging_v2(a)),
    "daily-ohlc": Endpoint("daily-ohlc", "daily-ohlc", "DailyOhlc (legacy v2)", "GET", config.SSI_DAILY_OHLC_URL, True, "data", lambda a: _v2_symbol_dates(a)),
    "intraday-ohlc": Endpoint("intraday-ohlc", "intraday-ohlc", "IntradayOhlc (legacy v2)", "GET", config.SSI_INTRADAY_OHLC_URL, True, "data", lambda a: _v2_symbol_dates(a, intraday=True)),
    "daily-index": Endpoint("daily-index", "daily-index", "DailyIndex (legacy v2)", "GET", config.SSI_DAILY_INDEX_URL, True, "data", lambda a: {"IndexId": a.index_code, "FromDate": _v2_dates(a)[0], "ToDate": _v2_dates(a)[1], **_paging_v2(a)} if a.index_code else (_ for _ in ()).throw(ParameterError("daily-index requires --index-code"))),
    "daily-stock-price": Endpoint("daily-stock-price", "daily-stock-price", "DailyStockPrice (legacy v2)", "GET", config.SSI_DAILY_STOCK_PRICE_URL, True, "data", lambda a: _v2_symbol_dates(a, market=True)),
}

RUN_ALL_ORDER = {
    "ssi_v3": ["securities-by-board", "securities-summary", "index-list", "index-summary", "daily-ohlc", "intraday-ohlc", "master-data"],
    "ssi_v2": [name for name in V2_ENDPOINTS if name != "access-token"],
}


def registry(source: str) -> dict[str, Endpoint]:
    return V3_ENDPOINTS if source == "ssi_v3" else V2_ENDPOINTS

# Backward-compatible import for callers that inspect the default registry.
ENDPOINTS = V3_ENDPOINTS
