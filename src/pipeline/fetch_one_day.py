import hashlib
import json
import logging
from datetime import date as Date, datetime, time
from zoneinfo import ZoneInfo
from typing import Any

from src.pipeline.date_utils import parse_ddmmyyyy

from src.database.client import SupabaseClient
from src.ssi.api import SSIApi
from src.intraday_value import calculate_trade_value
from src.validation.daily_validator import validate_daily_record
from src.validation.intraday_validator import validate_intraday_batch, validate_intraday_record
from src.validation.logging_utils import log_validation_result


logger = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UTC_TZ = ZoneInfo("UTC")


def fetch_daily_price(ssi: SSIApi, symbol: str, date: str) -> dict | None:
    """Fetch daily reference prices from SSI without transforming data."""
    return ssi.get_daily_price(symbol, date)


def fetch_intraday_candles(ssi: SSIApi, symbol: str, date: str) -> list[dict]:
    """Fetch intraday candles from SSI without transforming data."""
    candles = ssi.get_intraday(symbol, date)
    return candles or []


def _to_utc_iso_z(dt: datetime) -> str:
    return dt.astimezone(UTC_TZ).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(date_str: str, time_str: str) -> datetime | None:
    """Parse SSI local Vietnam candle time and return an aware UTC datetime."""
    base_date = _parse_base_date(date_str)
    if base_date is None:
        return None
    return _parse_candle_time(base_date, time_str)


def _parse_base_date(date_str: str) -> Date | None:
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return None


def _parse_candle_time(base_date: Date, time_str: Any) -> datetime | None:
    """Treat SSI IntradayOhlc Time as Asia/Ho_Chi_Minh and convert to UTC."""
    try:
        hour, minute, second = map(int, str(time_str).split(":"))
        local_dt = datetime.combine(base_date, time(hour, minute, second), tzinfo=VN_TZ)
        return local_dt.astimezone(UTC_TZ)
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



def _get_any(data: dict, *keys: str) -> Any:
    lower = {str(k).lower(): v for k, v in (data or {}).items()}
    for key in keys:
        if key in data:
            return data.get(key)
        value = lower.get(key.lower())
        if value is not None:
            return value
    return None

def _parse_trading_date(date_str: str) -> str | None:
    base_date = _parse_base_date(date_str)
    return base_date.isoformat() if base_date else None


def _payload_symbol(payload: dict) -> str | None:
    value = _get_any(payload, "Symbol", "symbol", "Ticker", "StockSymbol")
    return str(value).upper() if value not in (None, "") else None


def _payload_trading_date(payload: dict) -> str | None:
    value = _get_any(payload, "TradingDate", "tradingDate", "Date", "date", "TradingTime")
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
    requested = parse_ddmmyyyy(date).iso
    return _payload_symbol(payload) == symbol.upper() and _payload_trading_date(payload) == requested

def build_stock_daily_record(symbol: str, date: str, daily: dict) -> dict | None:
    trading_date = _parse_trading_date(date)
    if not trading_date:
        return None
    payload_date = _payload_trading_date(daily)
    if payload_date is not None and payload_date != trading_date:
        logger.warning("%s %s: SSI payload trading date %s does not match request; skipping stock_daily", symbol, date, payload_date)
        return None
    payload_symbol = _payload_symbol(daily)
    if payload_symbol is not None and payload_symbol != symbol.upper():
        logger.warning("%s %s: SSI payload symbol %s does not match request; skipping stock_daily", symbol, date, payload_symbol)
        return None
    mapping = {
        'price_change': ('PriceChange', 'Change'),
        'per_price_change': ('PerPriceChange', 'RatioChange'),
        'ceiling_price': ('CeilingPrice',),
        'floor_price': ('FloorPrice',),
        'ref_price': ('RefPrice',),
        'open_price': ('OpenPrice', 'Open'),
        'highest_price': ('HighestPrice', 'High', 'Highest'),
        'lowest_price': ('LowestPrice', 'Low', 'Lowest'),
        'close_price': ('ClosePrice', 'Close'),
        'average_price': ('AveragePrice', 'AvgPrice'),
        'close_price_adjusted': ('ClosePriceAdjusted', 'AdjustedClose', 'CloseAdjusted'),
        'total_match_vol': ('TotalMatchVol',),
        'total_match_val': ('TotalMatchVal',),
        'total_deal_vol': ('TotalDealVol',),
        'total_deal_val': ('TotalDealVal',),
        'total_traded_vol': ('TotalTradedVol', 'TotalVol'),
        'total_traded_value': ('TotalTradedValue', 'TotalVal'),
        'foreign_buy_vol_total': ('ForeignBuyVolTotal',),
        'foreign_sell_vol_total': ('ForeignSellVolTotal',),
        'foreign_buy_val_total': ('ForeignBuyValTotal',),
        'foreign_sell_val_total': ('ForeignSellValTotal',),
        'foreign_current_room': ('ForeignCurrentRoom',),
        'net_foreign_vol': ('Netforeivol', 'NetForeignVol', 'netbuysellvol'),
        'net_foreign_val': ('Netforeignval', 'NetForeignVal', 'netbuysellval'),
        'total_buy_trade': ('TotalBuyTrade',),
        'total_buy_trade_vol': ('TotalBuyTradeVol',),
        'total_sell_trade': ('TotalSellTrade',),
        'total_sell_trade_vol': ('TotalSellTradeVol',),
    }
    record = {'symbol': symbol, 'trading_date': trading_date, 'raw': daily}
    for out_key, keys in mapping.items():
        record[out_key] = _to_nullable_float(_get_any(daily, *keys))
    return record

def build_raw_daily_record(symbol: str, date: str, daily: dict) -> dict | None:
    trading_date = _parse_trading_date(date)
    if not trading_date:
        return None
    return {
        'symbol': symbol,
        'trading_date': trading_date,
        'data_hash': hashlib.sha256(json.dumps(daily, sort_keys=True).encode()).hexdigest(),
        'payload': daily,
    }

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
        time_iso = _to_utc_iso_z(dt)

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


def _deduplicate_intraday_records(records: list[dict]) -> list[dict]:
    """Keep the last input record for each symbol/timeframe/time key, then sort by time."""
    keyed: dict[tuple[Any, Any, Any], tuple[int, dict]] = {}
    for index, record in enumerate(records):
        keyed[(record.get("symbol"), record.get("timeframe"), record.get("time"))] = (index, record)
    return [record for _index, record in sorted(keyed.values(), key=lambda item: (item[1].get("time") or "", item[0]))]


def _log_ingest_summary(summary: dict) -> None:
    logger.info(
        "%s %s\ndaily:\n  valid: %s\n  errors: %s\n  warnings: %s\nintraday:\n  received: %s\n  valid: %s\n  rejected: %s\n  batch_errors: %s\n  batch_warnings: %s",
        summary["symbol"],
        summary["date"],
        "yes" if summary["daily_valid"] else "no",
        summary["daily_errors"],
        summary["daily_warnings"],
        summary["intraday_received"],
        summary["intraday_valid"],
        summary["intraday_rejected"],
        summary["intraday_batch_errors"],
        summary["intraday_batch_warnings"],
    )


def fetch_one_day_with_clients(
    ssi: SSIApi,
    db: SupabaseClient,
    symbol: str,
    date: str,
) -> int:
    """Fetch, transform, validate, and save one trading day using existing clients."""
    summary = {
        "symbol": symbol,
        "date": date,
        "daily_valid": False,
        "daily_errors": 0,
        "daily_warnings": 0,
        "intraday_received": 0,
        "intraday_valid": 0,
        "intraday_rejected": 0,
        "intraday_batch_errors": 0,
        "intraday_batch_warnings": 0,
    }
    daily = fetch_daily_price(ssi, symbol, date)
    if not daily:
        logger.warning("%s: không có dữ liệu ngày %s", symbol, date)
        _log_ingest_summary(summary)
        return 0

    raw_daily_record = build_raw_daily_record(symbol, date, daily)
    if raw_daily_record:
        db.upsert_raw_daily([raw_daily_record])

    stock_daily_record = build_stock_daily_record(symbol, date, daily)
    daily_validation = validate_daily_record(stock_daily_record) if stock_daily_record else None
    if daily_validation:
        summary["daily_valid"] = daily_validation.is_valid
        summary["daily_errors"] = len(daily_validation.errors)
        summary["daily_warnings"] = len(daily_validation.warnings)
        log_validation_result(daily_validation, "stock_daily", {"symbol": symbol, "trading_date": stock_daily_record.get("trading_date")})
    if stock_daily_record and daily_validation and daily_validation.is_valid:
        db.upsert_stock_daily([stock_daily_record])

    candles = fetch_intraday_candles(ssi, symbol, date)
    summary["intraday_received"] = len(candles)
    if not candles:
        logger.warning("%s: không có dữ liệu intraday", symbol)
        _log_ingest_summary(summary)
        return 0

    raw_records, clean_records = build_intraday_records(symbol, date, daily, candles)
    if raw_records:
        db.upsert_raw(raw_records)

    if not (stock_daily_record and daily_validation and daily_validation.is_valid):
        logger.error("%s %s: daily validation failed; skipping stock_intraday clean records", symbol, date)
        summary["intraday_rejected"] = len(clean_records)
        _log_ingest_summary(summary)
        return 0

    individual_valid_records: list[dict] = []
    for record in clean_records:
        result = validate_intraday_record(record)
        log_validation_result(result, "stock_intraday", {"symbol": symbol, "time": record.get("time")})
        if result.is_valid:
            individual_valid_records.append(record)

    batch_result = validate_intraday_batch(individual_valid_records, daily_record=stock_daily_record)
    log_validation_result(batch_result, "stock_intraday", {"symbol": symbol, "trading_date": stock_daily_record.get("trading_date")})
    records_to_save = individual_valid_records
    if any(issue.code == "INTRADAY_DUPLICATE_TIMESTAMP" for issue in batch_result.errors):
        records_to_save = _deduplicate_intraday_records(individual_valid_records)

    if records_to_save:
        db.upsert_intraday(records_to_save)
    count = len(records_to_save)
    summary["intraday_valid"] = count
    summary["intraday_rejected"] = len(clean_records) - len(individual_valid_records) + (len(individual_valid_records) - len(records_to_save))
    summary["intraday_batch_errors"] = len(batch_result.errors)
    summary["intraday_batch_warnings"] = len(batch_result.warnings)
    _log_ingest_summary(summary)
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
