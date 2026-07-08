from __future__ import annotations

from typing import Any

from src.database.client import SupabaseClient
from src.pipeline.date_utils import parse_ddmmyyyy
from src.ssi.api import SSIApi


def _get_any(data: dict, *keys: str) -> Any:
    lowered = {str(k).lower(): v for k, v in (data or {}).items()}
    for key in keys:
        if key in data:
            return data.get(key)
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _net(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def build_foreign_trading_record(symbol: str, date: str, row: dict) -> dict | None:
    trading_date = parse_ddmmyyyy(date).iso
    row_symbol = _get_any(row, "Symbol", "symbol", "Ticker", "ticker") or symbol
    buy_vol = _to_float(_get_any(row, "ForeignBuyVolTotal", "ForeignBuyVolume", "BuyVolume", "buyVolume", "foreign_buy_vol"))
    sell_vol = _to_float(_get_any(row, "ForeignSellVolTotal", "ForeignSellVolume", "SellVolume", "sellVolume", "foreign_sell_vol"))
    buy_val = _to_float(_get_any(row, "ForeignBuyValTotal", "ForeignBuyValue", "BuyValue", "buyValue", "foreign_buy_val"))
    sell_val = _to_float(_get_any(row, "ForeignSellValTotal", "ForeignSellValue", "SellValue", "sellValue", "foreign_sell_val"))
    net_vol = _to_float(_get_any(row, "Netforeivol", "NetForeignVol", "netbuysellvol", "NetVolume", "netVolume"))
    net_val = _to_float(_get_any(row, "Netforeignval", "NetForeignVal", "netbuysellval", "NetValue", "netValue"))
    room = _to_float(_get_any(row, "ForeignCurrentRoom", "CurrentRoom", "ForeignRoom", "foreign_room"))
    if net_vol is None:
        net_vol = _net(buy_vol, sell_vol)
    if net_val is None:
        net_val = _net(buy_val, sell_val)
    if all(value is None for value in (buy_vol, sell_vol, buy_val, sell_val, net_vol, net_val, room)):
        return None
    return {
        "symbol": str(row_symbol).upper(),
        "trading_date": trading_date,
        "foreign_buy_vol": buy_vol,
        "foreign_sell_vol": sell_vol,
        "foreign_buy_val": buy_val,
        "foreign_sell_val": sell_val,
        "net_foreign_vol": net_vol,
        "net_foreign_val": net_val,
        "foreign_room": room,
        "foreign_current_room": room,
        "buy_vol": buy_vol,
        "sell_vol": sell_vol,
        "net_vol": net_vol,
        "raw": row,
    }


def fetch_foreign_for_symbol(ssi: SSIApi, symbol: str, date: str, daily: dict | None = None) -> dict | None:
    rows = ssi.get_foreign_trading(symbol=symbol, date=date)
    if not rows and daily:
        rows = [daily]
    for row in rows:
        record = build_foreign_trading_record(symbol, date, row)
        if record:
            return record
    return None


def fetch_foreign_trading_day(date: str, symbols: list[str] | None = None, ssi: SSIApi | None = None, db: SupabaseClient | None = None) -> int:
    ssi = ssi or SSIApi()
    db = db or SupabaseClient()
    symbols = symbols or db.get_symbols()
    records = []
    for symbol in symbols:
        record = fetch_foreign_for_symbol(ssi, symbol, date)
        if record:
            records.append(record)
        else:
            print(f"  ⚠️ {symbol}: no foreign trading data for {date}")
    if records:
        db.upsert_foreign(records)
    print(f"🌐 foreign_trading upserted: {len(records)}")
    return len(records)
