import hashlib
import json
import logging
from datetime import date as Date, datetime, time
from typing import Any

from src.database.client import SupabaseClient
from src.ssi.api import SSIApi
from src.intraday_value import calculate_trade_value


logger = logging.getLogger(__name__)


logger = logging.getLogger(__name__)


def fetch_daily_price(ssi: SSIApi, symbol: str, date: str) -> dict | None:
    """Fetch daily reference prices from SSI without transforming data."""
    return ssi.get_daily_price(symbol, date)


def fetch_intraday_candles(ssi: SSIApi, symbol: str, date: str) -> list[dict]:
    """Fetch intraday candles from SSI without transforming data."""
    candles = ssi.get_intraday(symbol, date)
    return candles or []


def parse_time(date_str: str, time_str: str) -> datetime | None:
    """Convert DD/MM/YYYY and HH:MM:SS into a datetime object."""
    try:
        base_date = datetime.strptime(date_str, "%d/%m/%Y").date()
        hour, minute, second = map(int, str(time_str).split(":"))
        return datetime.combine(base_date, time(hour, minute, second))
    except (ValueError, TypeError):
        return None


def _parse_base_date(date_str: str) -> Date | None:
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return None


def _parse_candle_time(base_date: Date, time_str: Any) -> datetime | None:
    try:
        hour, minute, second = map(int, str(time_str).split(":"))
        return datetime.combine(base_date, time(hour, minute, second))
    except (ValueError, TypeError):
        return None


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(default if _is_missing(value) else value)
    except (ValueError, TypeError):
        return default


def _to_nullable_float(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _to_nullable_int(value: Any) -> int | None:
    if _is_missing(value):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None



def build_intraday_records(
    symbol: str,
    date: str,
    daily: dict,
    candles: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Transform SSI daily and intraday API data into DB-ready records."""
    raw_records: list[dict] = []
    clean_records: list[dict] = []
    base_date = _parse_base_date(date)
    if base_date is None:
        print(f"  ⚠️ {symbol}: ngày không hợp lệ: {date}")
        return raw_records, clean_records

    reference_price = _to_float(daily.get('RefPrice', 0))
    ceiling_price = _to_float(daily.get('CeilingPrice', 0))
    floor_price = _to_float(daily.get('FloorPrice', 0))
    debug_samples: list[dict] = []

    for candle in candles:
        time_str = candle.get('Time', '')
        dt = _parse_candle_time(base_date, time_str)
        if dt is None:
            print(f"  ⚠️ {symbol}: bỏ qua candle lỗi timestamp: {time_str}")
            continue

        current_volume = _to_nullable_int(candle.get('Volume'))
        open_price = _to_nullable_float(candle.get('Open'))
        high_price = _to_nullable_float(candle.get('High'))
        low_price = _to_nullable_float(candle.get('Low'))
        close_price = _to_nullable_float(candle.get('Close'))
        intraday_value = calculate_trade_value(close_price, current_volume)
        time_iso = dt.isoformat()

        base_record = {
            'symbol': symbol,
            'time': time_iso,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': current_volume,
        }

        if len(debug_samples) < 5:
            debug_samples.append({
                **base_record,
                'value': intraday_value,
                'value_type': type(intraday_value).__name__,
            })

        raw_records.append({
            **base_record,
            'data_hash': hashlib.sha256(
                json.dumps(candle, sort_keys=True).encode()
            ).hexdigest(),
        })

        clean_records.append({
            **base_record,
            'timeframe': '1m',
            'value': intraday_value,
            'reference_price': reference_price,
            'ceiling_price': ceiling_price,
            'floor_price': floor_price,
        })

    if debug_samples:
        logger.debug("Normalized intraday sample rows for %s %s: %s", symbol, date, debug_samples)

    return raw_records, clean_records


def save_intraday_records(
    db: SupabaseClient,
    raw_records: list[dict],
    clean_records: list[dict],
) -> int:
    """Persist transformed intraday records and return the clean candle count."""
    if raw_records:
        db.upsert_raw(raw_records)

    if clean_records:
        db.upsert_intraday(clean_records)

    return len(clean_records)


def fetch_one_day_with_clients(
    ssi: SSIApi,
    db: SupabaseClient,
    symbol: str,
    date: str,
) -> int:
    """Fetch, transform, and save one trading day using existing clients."""
    daily = fetch_daily_price(ssi, symbol, date)
    if not daily:
        print(f"  ⚠️ {symbol}: không có dữ liệu ngày {date}")
        return 0

    candles = fetch_intraday_candles(ssi, symbol, date)
    if not candles:
        print(f"  ⚠️ {symbol}: không có dữ liệu intraday")
        return 0

    raw_records, clean_records = build_intraday_records(symbol, date, daily, candles)
    count = save_intraday_records(db, raw_records, clean_records)
    print(f"  ✅ {symbol}: {count} candles")
    return count


def fetch_one_day(symbol: str, date: str) -> int:
    """
    Lấy dữ liệu 1 ngày cho 1 mã.

    Args:
        symbol: Mã chứng khoán (VD: 'SSI')
        date: DD/MM/YYYY
    """
    ssi = SSIApi()
    db = SupabaseClient()
    return fetch_one_day_with_clients(ssi, db, symbol, date)
