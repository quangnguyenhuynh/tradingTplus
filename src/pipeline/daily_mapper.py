"""SSI v2 DailyStockPrice compatibility wrappers over the shared mapping engine."""
import hashlib
import json
import logging
from datetime import datetime
from typing import Any

from src.data_contracts import map_record
from src.pipeline.date_utils import parse_ddmmyyyy, trading_date_iso

logger = logging.getLogger(__name__)

def get_payload_value(data: dict, *keys: str) -> Any:
    lower = {str(key).casefold(): value for key, value in (data or {}).items()}
    present = [(key, lower[key.casefold()]) for key in keys if key.casefold() in lower]
    return present[0][1] if present else None

def to_nullable_float(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool): return None
    try:
        number = float(value)
        return number if number == number and abs(number) != float("inf") else None
    except (ValueError, TypeError): return None

def to_nullable_reference_price(value: Any) -> float | None:
    number = to_nullable_float(value)
    return None if number == 0 else number

def payload_symbol(payload: dict) -> str | None:
    value = get_payload_value(payload, "Symbol", "Ticker", "StockSymbol")
    return str(value).upper() if value not in (None, "") else None

def payload_trading_date(payload: dict) -> str | None:
    value = get_payload_value(payload, "TradingDate", "Date", "TradingTime")
    if value in (None, ""): return None
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try: return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError: continue
    return None

def payload_matches_request(payload: dict, symbol: str, date: str) -> bool:
    return payload_symbol(payload) == symbol.upper() and payload_trading_date(payload) == parse_ddmmyyyy(date).iso

def map_stock_daily_record(symbol: str, date: str, daily: dict):
    requested_date = trading_date_iso(date)
    if not requested_date:
        return None, {"source":"ssi_v2","dataset":"stock_daily","records_received":1,"records_valid":0,"records_rejected":1,"errors":[{"code":"INVALID_REQUEST_DATE"}]}
    source_date, source_symbol = payload_trading_date(daily), payload_symbol(daily)
    if source_date is not None and source_date != requested_date:
        logger.warning("%s %s: SSI payload trading date %s does not match request; skipping stock_daily", symbol, date, source_date); return None, {"source":"ssi_v2","dataset":"stock_daily","records_received":1,"records_valid":0,"records_rejected":1,"errors":[{"code":"REQUEST_DATE_MISMATCH"}]}
    if source_symbol is not None and source_symbol != symbol.upper():
        logger.warning("%s %s: SSI payload symbol %s does not match request; skipping stock_daily", symbol, date, source_symbol); return None, {"source":"ssi_v2","dataset":"stock_daily","records_received":1,"records_valid":0,"records_rejected":1,"errors":[{"code":"REQUEST_SYMBOL_MISMATCH"}]}
    result = map_record("ssi_v2", "stock_daily", daily, {"symbol": symbol, "date": date})
    candidate = dict(result.candidate) if result.candidate else None
    if candidate is not None: candidate["raw"] = daily
    return candidate, result.report

def build_stock_daily_record(symbol: str, date: str, daily: dict) -> dict | None:
    return map_stock_daily_record(symbol, date, daily)[0]

def build_raw_daily_record(symbol: str, date: str, daily: dict) -> dict | None:
    requested_date = trading_date_iso(date)
    if not requested_date: return None
    return {"symbol": symbol, "trading_date": requested_date, "data_hash": hashlib.sha256(json.dumps(daily, sort_keys=True).encode()).hexdigest(), "payload": daily}
