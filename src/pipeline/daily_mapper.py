"""Pure DailyStockPrice payload-to-record transformations."""
import hashlib
import json
import logging
from datetime import datetime
from typing import Any

from src.pipeline.date_utils import parse_ddmmyyyy, trading_date_iso

logger = logging.getLogger(__name__)


def get_payload_value(data: dict, *keys: str) -> Any:
    lower = {str(key).lower(): value for key, value in (data or {}).items()}
    for key in keys:
        if key in data:
            return data.get(key)
        value = lower.get(key.lower())
        if value is not None:
            return value
    return None


def to_nullable_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def to_nullable_reference_price(value: Any) -> float | None:
    """Map missing, invalid, and SSI zero placeholders to unknown price context."""
    number = to_nullable_float(value)
    return None if number == 0 else number


def payload_symbol(payload: dict) -> str | None:
    value = get_payload_value(payload, "Symbol", "symbol", "Ticker", "StockSymbol")
    return str(value).upper() if value not in (None, "") else None


def payload_trading_date(payload: dict) -> str | None:
    value = get_payload_value(payload, "TradingDate", "tradingDate", "Date", "date", "TradingTime")
    if value in (None, ""):
        return None
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def payload_matches_request(payload: dict, symbol: str, date: str) -> bool:
    return payload_symbol(payload) == symbol.upper() and payload_trading_date(payload) == parse_ddmmyyyy(date).iso


def build_stock_daily_record(symbol: str, date: str, daily: dict) -> dict | None:
    requested_date = trading_date_iso(date)
    if not requested_date:
        return None
    source_date = payload_trading_date(daily)
    if source_date is not None and source_date != requested_date:
        logger.warning("%s %s: SSI payload trading date %s does not match request; skipping stock_daily", symbol, date, source_date)
        return None
    source_symbol = payload_symbol(daily)
    if source_symbol is not None and source_symbol != symbol.upper():
        logger.warning("%s %s: SSI payload symbol %s does not match request; skipping stock_daily", symbol, date, source_symbol)
        return None
    mapping = {
        "price_change": ("PriceChange", "Change"), "per_price_change": ("PerPriceChange", "RatioChange"),
        "ceiling_price": ("CeilingPrice",), "floor_price": ("FloorPrice",), "ref_price": ("RefPrice",),
        "open_price": ("OpenPrice", "Open"), "highest_price": ("HighestPrice", "High", "Highest"),
        "lowest_price": ("LowestPrice", "Low", "Lowest"), "close_price": ("ClosePrice", "Close"),
        "average_price": ("AveragePrice", "AvgPrice"), "close_price_adjusted": ("ClosePriceAdjusted", "AdjustedClose", "CloseAdjusted"),
        "total_match_vol": ("TotalMatchVol",), "total_match_val": ("TotalMatchVal",), "total_deal_vol": ("TotalDealVol",),
        "total_deal_val": ("TotalDealVal",), "total_traded_vol": ("TotalTradedVol", "TotalVol"),
        "total_traded_value": ("TotalTradedValue", "TotalVal"), "foreign_buy_vol_total": ("ForeignBuyVolTotal",),
        "foreign_sell_vol_total": ("ForeignSellVolTotal",), "foreign_buy_val_total": ("ForeignBuyValTotal",),
        "foreign_sell_val_total": ("ForeignSellValTotal",), "foreign_current_room": ("ForeignCurrentRoom",),
        "net_foreign_vol": ("Netforeivol", "NetForeignVol", "netbuysellvol"), "net_foreign_val": ("Netforeignval", "NetForeignVal", "netbuysellval"),
        "total_buy_trade": ("TotalBuyTrade",), "total_buy_trade_vol": ("TotalBuyTradeVol",),
        "total_sell_trade": ("TotalSellTrade",), "total_sell_trade_vol": ("TotalSellTradeVol",),
    }
    record = {"symbol": symbol, "trading_date": requested_date, "raw": daily}
    record.update({output: to_nullable_float(get_payload_value(daily, *keys)) for output, keys in mapping.items()})
    for field in ("ref_price", "ceiling_price", "floor_price"):
        record[field] = to_nullable_reference_price(record[field])
    return record


def build_raw_daily_record(symbol: str, date: str, daily: dict) -> dict | None:
    requested_date = trading_date_iso(date)
    if not requested_date:
        return None
    return {"symbol": symbol, "trading_date": requested_date, "data_hash": hashlib.sha256(json.dumps(daily, sort_keys=True).encode()).hexdigest(), "payload": daily}
