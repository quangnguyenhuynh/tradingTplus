"""Pure SSI 1-minute candle normalization."""
import hashlib
import json
import logging
from datetime import date as Date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from src.intraday_value import calculate_trade_value

logger = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UTC_TZ = ZoneInfo("UTC")


def parse_time(date_str: str, time_str: str) -> datetime | None:
    """Treat SSI candle time as Vietnam local time and return UTC."""
    try:
        base_date = datetime.strptime(date_str, "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return None
    return parse_candle_time(base_date, time_str)


def parse_candle_time(base_date: Date, time_str: Any) -> datetime | None:
    try:
        hour, minute, second = map(int, str(time_str).split(":"))
        return datetime.combine(base_date, time(hour, minute, second), tzinfo=VN_TZ).astimezone(UTC_TZ)
    except (ValueError, TypeError):
        return None


def nullable_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def nullable_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def daily_context_payload(record: dict | None) -> dict:
    if not record:
        return {}
    return {"RefPrice": record.get("ref_price"), "CeilingPrice": record.get("ceiling_price"), "FloorPrice": record.get("floor_price"), **record}


def build_intraday_records(symbol: str, date: str, daily: dict | None, candles: list[dict]) -> tuple[list[dict], list[dict]]:
    """Map source candles to raw and clean records; invalid timestamps are rejected."""
    try:
        base_date = datetime.strptime(date, "%d/%m/%Y").date()
    except (ValueError, TypeError):
        logger.warning("%s: invalid trading date: %s", symbol, date)
        return [], []
    daily = daily or {}
    reference = nullable_float(daily.get("RefPrice", daily.get("ref_price")))
    ceiling = nullable_float(daily.get("CeilingPrice", daily.get("ceiling_price")))
    floor = nullable_float(daily.get("FloorPrice", daily.get("floor_price")))
    raw_records: list[dict] = []
    clean_records: list[dict] = []
    debug_samples: list[dict] = []
    for candle in candles:
        source_time = candle.get("Time", "")
        timestamp = parse_candle_time(base_date, source_time)
        if timestamp is None:
            logger.warning("%s: rejecting candle with invalid timestamp: %s", symbol, source_time)
            continue
        volume = nullable_int(candle.get("Volume"))
        close = nullable_float(candle.get("Close"))
        base = {"symbol": symbol, "time": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"), "open": nullable_float(candle.get("Open")), "high": nullable_float(candle.get("High")), "low": nullable_float(candle.get("Low")), "close": close, "volume": volume}
        estimated_value = calculate_trade_value(close, volume)
        raw_records.append({**base, "payload": candle, "data_hash": hashlib.sha256(json.dumps(candle, sort_keys=True).encode()).hexdigest()})
        clean_records.append({**base, "timeframe": "1m", "value": estimated_value, "reference_price": reference, "ceiling_price": ceiling, "floor_price": floor})
        if len(debug_samples) < 5:
            debug_samples.append({**base, "value": estimated_value, "value_type": type(estimated_value).__name__})
    if debug_samples:
        logger.debug("Normalized intraday sample rows for %s %s: %s", symbol, date, debug_samples)
    return raw_records, clean_records


def deduplicate_intraday_records(records: list[dict]) -> list[dict]:
    """Keep the last row for each persisted stock_intraday conflict key."""
    keyed: dict[tuple[Any, Any, Any], tuple[int, dict]] = {}
    for index, record in enumerate(records):
        keyed[(record.get("symbol"), record.get("timeframe"), record.get("time"))] = (index, record)
    return [record for _, record in sorted(keyed.values(), key=lambda item: (item[1].get("time") or "", item[0]))]
