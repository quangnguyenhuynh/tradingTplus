from typing import Any
from src.database.client import SupabaseClient
from src.ssi.api import SSIApi
from src.pipeline.fetch_one_day import _to_nullable_float, _parse_trading_date

IMPORTANT_INDEX_CODES = ["VNINDEX", "VN30", "HNXIndex", "HNX30", "HNXUpcomIndex", "UPCOMIndex"]


def _get_any(data: dict, *keys: str) -> Any:
    lower = {str(k).lower(): v for k, v in (data or {}).items()}
    for key in keys:
        if key in data:
            return data.get(key)
        if key.lower() in lower:
            return lower[key.lower()]
    return None


def map_index_record(item: dict) -> dict | None:
    code = _get_any(item, "IndexCode", "indexCode", "Code")
    if not code:
        return None
    return {"index_code": code, "index_name": _get_any(item, "IndexName", "Name"), "exchange": _get_any(item, "Exchange"), "raw": item}


def sync_indexes(ssi: SSIApi | None = None, db: SupabaseClient | None = None) -> list[str]:
    ssi = ssi or SSIApi()
    db = db or SupabaseClient()
    rows = []
    for exchange in ("HOSE", "HNX", "UPCOM"):
        rows.extend(ssi.get_index_list(exchange=exchange))
    records = [rec for rec in (map_index_record(row) for row in rows) if rec]
    if records:
        db.upsert_indexes(records)
    return [rec["index_code"] for rec in records]


def sync_index_components(index_codes: list[str] | None = None, ssi: SSIApi | None = None, db: SupabaseClient | None = None) -> int:
    ssi = ssi or SSIApi()
    db = db or SupabaseClient()
    records = []
    for code in (index_codes or IMPORTANT_INDEX_CODES):
        for row in ssi.get_index_components(code):
            symbol = _get_any(row, "Symbol", "symbol", "StockSymbol")
            if symbol:
                records.append({"index_code": code, "symbol": symbol, "exchange": _get_any(row, "Exchange"), "raw": row})
    if records:
        db.upsert_index_components(records)
    return len(records)


def build_index_daily_record(index_code: str, date: str, item: dict) -> dict | None:
    trading_date = _parse_trading_date(date)
    if not trading_date:
        return None
    mapping = {
        "index_value": ("IndexValue", "Value"), "change": ("Change",), "ratio_change": ("RatioChange",),
        "total_trade": ("TotalTrade",), "total_match_vol": ("TotalMatchVol",), "total_match_val": ("TotalMatchVal",),
        "total_deal_vol": ("TotalDealVol",), "total_deal_val": ("TotalDealVal",), "total_vol": ("TotalVol",),
        "total_val": ("TotalVal",), "advances": ("Advances",), "no_changes": ("NoChanges",),
        "declines": ("Declines",), "ceilings": ("Ceilings",), "floors": ("Floors",),
    }
    record = {
        "index_code": _get_any(item, "IndexCode", "indexCode") or index_code,
        "trading_date": trading_date,
        "type_index": _get_any(item, "TypeIndex"), "index_name": _get_any(item, "IndexName"),
        "trading_session": _get_any(item, "TradingSession"), "market": _get_any(item, "Market"),
        "exchange": _get_any(item, "Exchange"), "raw": item,
    }
    for key, names in mapping.items():
        record[key] = _to_nullable_float(_get_any(item, *names))
    return record


def fetch_daily_indexes(date: str, index_codes: list[str] | None = None, ssi: SSIApi | None = None, db: SupabaseClient | None = None) -> int:
    ssi = ssi or SSIApi()
    db = db or SupabaseClient()
    records = []
    for code in (index_codes or IMPORTANT_INDEX_CODES):
        item = ssi.get_daily_index(code, date)
        if item:
            rec = build_index_daily_record(code, date, item)
            if rec:
                records.append(rec)
    if records:
        db.upsert_index_daily(records)
    return len(records)
