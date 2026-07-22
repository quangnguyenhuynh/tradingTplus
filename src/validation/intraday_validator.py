from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src.validation.models import ValidationIssue, ValidationResult

PRICE_TOLERANCE = 1e-6
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UTC_TZ = ZoneInfo("UTC")
MORNING_START = time(9, 0)
MORNING_CONTINUOUS_END = time(11, 29)
AFTERNOON_START = time(13, 0)
AFTERNOON_CONTINUOUS_END = time(14, 29)
SESSION_END = time(15, 0)
REQUIRED_FIELDS = ["symbol", "time", "timeframe", "open", "high", "low", "close", "volume"]


def _issue(code: str, message: str, severity: str, field: str | None = None, actual: Any = None, expected: Any = None) -> ValidationIssue:
    return ValidationIssue(code, message, severity, field, actual, expected)


def _missing(value: Any) -> bool:
    return value is None or value == ""


def _num(value: Any) -> float | None:
    if _missing(value) or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    utc = dt.astimezone(UTC_TZ)
    if utc.utcoffset() != timedelta(0):
        return None
    return utc


def _result(errors: list[ValidationIssue], warnings: list[ValidationIssue]) -> ValidationResult:
    return ValidationResult(is_valid=not errors, errors=errors, warnings=warnings)


def _in_trading_session(dt_utc: datetime) -> bool:
    local_t = dt_utc.astimezone(VN_TZ).time()
    return (MORNING_START <= local_t <= time(11, 30)) or (AFTERNOON_START <= local_t <= SESSION_END)


def _minute_bucket(dt_utc: datetime) -> datetime:
    """Normalize only the validation view; persisted source timestamps stay intact."""
    return dt_utc.replace(second=0, microsecond=0)


def _is_continuous_minute(dt_utc: datetime) -> bool:
    local_t = dt_utc.astimezone(VN_TZ).time()
    return (MORNING_START <= local_t <= MORNING_CONTINUOUS_END) or (
        AFTERNOON_START <= local_t <= AFTERNOON_CONTINUOUS_END
    )


def _missing_continuous_minutes(prev_utc: datetime, next_utc: datetime) -> int:
    """Count only absent minute buckets that belong to continuous trading."""
    current = _minute_bucket(prev_utc) + timedelta(minutes=1)
    end = _minute_bucket(next_utc)
    missing = 0
    while current < end:
        if _is_continuous_minute(current):
            missing += 1
        current += timedelta(minutes=1)
    return missing


def validate_intraday_record(record: dict) -> ValidationResult:
    if not isinstance(record, dict):
        raise TypeError("intraday record must be a dict")
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    for field in REQUIRED_FIELDS:
        if field not in record or _missing(record.get(field)):
            errors.append(_issue("INTRADAY_REQUIRED_FIELD_MISSING", f"Required field {field} is missing", "error", field, record.get(field), "non-empty value"))
    if record.get("timeframe") not in (None, "", "1m"):
        errors.append(_issue("INTRADAY_INVALID_TIMEFRAME", "timeframe must be 1m", "error", "timeframe", record.get("timeframe"), "1m"))

    ts = _parse_ts(record.get("time"))
    if ts is None:
        errors.append(_issue("INTRADAY_INVALID_TIMESTAMP", "time must be parseable timezone-aware UTC timestamp", "error", "time", record.get("time"), "UTC ISO timestamp"))

    values = {f: _num(record.get(f)) for f in ["open", "high", "low", "close"]}
    for field, value in values.items():
        if value is not None and value <= 0:
            errors.append(_issue("INTRADAY_NON_POSITIVE_PRICE", f"{field} must be positive", "error", field, value, "> 0"))
    vol = _num(record.get("volume"))
    if vol is not None and vol < 0:
        errors.append(_issue("INTRADAY_NEGATIVE_VOLUME", "volume must not be negative", "error", "volume", vol, ">= 0"))
    val = _num(record.get("value"))
    if val is not None and val < 0:
        errors.append(_issue("INTRADAY_NEGATIVE_VALUE", "value must not be negative", "error", "value", val, ">= 0"))

    o, h, l, c = values["open"], values["high"], values["low"], values["close"]
    if None not in (o, h, l, c):
        if h < max(o, c, l):
            errors.append(_issue("INTRADAY_INVALID_OHLC", "high is below an OHLC component", "error", "high", h, f">= {max(o, c, l)}"))
        if l > min(o, c, h):
            errors.append(_issue("INTRADAY_INVALID_OHLC", "low is above an OHLC component", "error", "low", l, f"<= {min(o, c, h)}"))
        if h < l:
            errors.append(_issue("INTRADAY_INVALID_OHLC", "high is below low", "error", "high", h, f">= {l}"))

    floor = _num(record.get("floor_price")); ceiling = _num(record.get("ceiling_price"))
    if None not in (floor, ceiling):
        for field, value in values.items():
            if value is not None and not (floor - PRICE_TOLERANCE <= value <= ceiling + PRICE_TOLERANCE):
                errors.append(_issue("INTRADAY_PRICE_OUTSIDE_LIMIT", f"{field} is outside intraday price limits", "error", field, value, f"{floor} <= {field} <= {ceiling}"))

    return _result(errors, warnings)


def validate_intraday_batch(records: list[dict], daily_record: dict | None = None) -> ValidationResult:
    if not isinstance(records, list):
        raise TypeError("intraday records must be a list")
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    if not records:
        warnings.append(_issue("INTRADAY_EMPTY_BATCH", "intraday batch is empty", "warning", actual=0, expected="> 0 records"))
        return _result(errors, warnings)

    parsed = [(i, r, _parse_ts(r.get("time"))) for i, r in enumerate(records)]
    parsed_valid = [(i, r, ts) for i, r, ts in parsed if ts is not None]
    keys: dict[tuple[Any, Any, Any], int] = {}
    for i, r, ts in parsed_valid:
        key = (r.get("symbol"), r.get("timeframe"), r.get("time"))
        if key in keys:
            errors.append(_issue("INTRADAY_DUPLICATE_TIMESTAMP", "Duplicate symbol/timeframe/time candle", "error", "time", r.get("time"), "unique symbol + timeframe + time"))
        keys[key] = i

    sorted_valid = sorted(parsed_valid, key=lambda item: item[2])
    if [i for i, _, _ in sorted_valid] != [i for i, _, _ in parsed_valid]:
        warnings.append(_issue("INTRADAY_UNSORTED_INPUT", "Input intraday candles are not sorted by timestamp", "warning", "time", [r.get("time") for _, r, _ in parsed_valid], "ascending time"))

    for _, r, ts in parsed_valid:
        if not _in_trading_session(ts):
            warnings.append(_issue("INTRADAY_OUTSIDE_TRADING_SESSION", "Candle is outside configured Vietnam trading sessions", "warning", "time", r.get("time"), "09:00-11:30 or 13:00-15:00 Asia/Ho_Chi_Minh"))

    for (prev_i, prev_r, prev_ts), (next_i, next_r, next_ts) in zip(sorted_valid, sorted_valid[1:]):
        if prev_r.get("symbol") != next_r.get("symbol") or prev_r.get("timeframe") != next_r.get("timeframe"):
            continue
        if prev_ts.astimezone(VN_TZ).date() != next_ts.astimezone(VN_TZ).date():
            continue
        missing_minutes = _missing_continuous_minutes(prev_ts, next_ts)
        if missing_minutes:
            warnings.append(_issue("INTRADAY_MISSING_INTERVAL", "Missing one or more 1m candles inside continuous trading sessions", "warning", "time", {"previous_time": prev_r.get("time"), "next_time": next_r.get("time"), "missing_minutes": missing_minutes}, "consecutive 1m candles inside 09:00-11:29 or 13:00-14:29 Asia/Ho_Chi_Minh"))

    if daily_record and sorted_valid:
        last = sorted_valid[-1][1]
        last_close = _num(last.get("close")); daily_close = _num(daily_record.get("close_price"))
        if None not in (last_close, daily_close) and abs(last_close - daily_close) > max(1e-6, abs(daily_close) * 0.0001):
            warnings.append(_issue("INTRADAY_DAILY_CLOSE_MISMATCH", "Last intraday close differs from daily close_price", "warning", "close", last_close, daily_close))
        daily_vol = _num(daily_record.get("total_match_vol"))
        volumes = [_num(r.get("volume")) for _, r, _ in parsed_valid]
        if daily_vol is not None and all(v is not None for v in volumes):
            total = sum(v for v in volumes if v is not None)
            if abs(total - daily_vol) > 1e-6:
                warnings.append(_issue("INTRADAY_DAILY_VOLUME_MISMATCH", "Intraday volume sum differs from daily total_match_vol", "warning", "volume", total, daily_vol))

    return _result(errors, warnings)
