from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src.validation.models import ValidationIssue, ValidationResult

UTC_TZ = ZoneInfo("UTC")
SUPPORTED_STREAM_TYPES = {"F", "X-QUOTE", "QUOTE", "X-TRADE", "TRADE", "R", "MI", "B"}


def _issue(code: str, message: str, severity: str = "error", field: str | None = None, actual: Any = None, expected: Any = None) -> ValidationIssue:
    return ValidationIssue(code, message, severity, field, actual, expected)


def _result(errors: list[ValidationIssue], warnings: list[ValidationIssue]) -> ValidationResult:
    return ValidationResult(is_valid=not errors, errors=errors, warnings=warnings)


def _missing(value: Any) -> bool:
    return value is None or value == ""


def _num(value: Any) -> float | None:
    if _missing(value) or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


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


def _validate_common(record: Any, stream_type: str) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    if not isinstance(record, dict):
        return [_issue("STREAM_RECORD_NOT_DICT", "stream record must be a dict", "error", actual=type(record).__name__, expected="dict")], warnings
    if stream_type not in SUPPORTED_STREAM_TYPES:
        errors.append(_issue("STREAM_UNSUPPORTED_TYPE", "stream type is not supported", "error", "rtype", stream_type, sorted(SUPPORTED_STREAM_TYPES)))
    if _parse_ts(record.get("time")) is None:
        errors.append(_issue("STREAM_INVALID_SOURCE_TIMESTAMP", "source time must be parseable timezone-aware UTC timestamp", "error", "time", record.get("time"), "UTC ISO timestamp from source"))
    for field, value in record.items():
        if isinstance(value, float) and not math.isfinite(value):
            errors.append(_issue("STREAM_NON_FINITE_NUMERIC", "numeric field must be finite", "error", field, value, "finite number"))
    return errors, warnings


def _check_non_negative(record: dict[str, Any], fields: list[str], errors: list[ValidationIssue]) -> None:
    for field in fields:
        value = _num(record.get(field))
        if value is not None and value < 0:
            errors.append(_issue("STREAM_NEGATIVE_NUMERIC", f"{field} must not be negative", "error", field, value, ">= 0"))


def _check_positive(record: dict[str, Any], fields: list[str], errors: list[ValidationIssue]) -> None:
    for field in fields:
        value = _num(record.get(field))
        if value is not None and value <= 0:
            errors.append(_issue("STREAM_NON_POSITIVE_PRICE", f"{field} must be positive when present", "error", field, value, "> 0"))


def validate_stream_record(record: Any, stream_type: str) -> ValidationResult:
    errors, warnings = _validate_common(record, stream_type)
    if errors and not isinstance(record, dict):
        return _result(errors, warnings)
    assert isinstance(record, dict)

    canonical = {"QUOTE": "X-QUOTE", "TRADE": "X-TRADE"}.get(stream_type, stream_type)
    symbol_required = {"F", "X-QUOTE", "X-TRADE", "R", "B"}
    if canonical in symbol_required and _missing(record.get("symbol")):
        errors.append(_issue("STREAM_SYMBOL_MISSING", "symbol is required for this stream type", "error", "symbol", record.get("symbol"), "non-empty symbol"))
    if canonical == "MI" and _missing(record.get("index_code")):
        errors.append(_issue("STREAM_INDEX_CODE_MISSING", "index_code is required for index stream", "error", "index_code", record.get("index_code"), "non-empty index code"))

    if canonical in {"X-QUOTE", "X-TRADE"}:
        _check_positive(record, ["ceiling", "floor", "ref_price", "open", "close", "high", "low", "avg_price", "last_price", "est_matched_price"], errors)
        _check_non_negative(record, ["last_vol", "total_vol", "total_val"], errors)
    if canonical == "X-QUOTE":
        for i in range(1, 11):
            _check_positive(record, [f"bid_price_{i}", f"ask_price_{i}"], errors)
            _check_non_negative(record, [f"bid_vol_{i}", f"ask_vol_{i}"], errors)
    if canonical == "R":
        _check_non_negative(record, ["total_room", "current_room", "foreign_buy_vol", "foreign_sell_vol", "foreign_buy_val", "foreign_sell_val", "net_foreign_vol", "net_foreign_val"], errors)
        total_room = _num(record.get("total_room")); current_room = _num(record.get("current_room"))
        if total_room is not None and current_room is not None and current_room > total_room:
            errors.append(_issue("STREAM_ROOM_EXCEEDS_TOTAL", "current_room must not exceed total_room", "error", "current_room", current_room, f"<= {total_room}"))
    if canonical == "MI":
        _check_positive(record, ["index_value", "index_val_est", "prior_index_value"], errors)
        _check_non_negative(record, ["total_trade", "total_qtty", "total_value", "total_qtty_pt", "total_value_pt", "total_qtty_od", "total_value_od", "all_qty", "all_value", "advances", "no_changes", "declines", "ceilings", "floors"], errors)
    if canonical == "B":
        _check_positive(record, ["open", "high", "low", "close"], errors)
        _check_non_negative(record, ["volume", "value"], errors)
        o, h, l, c = (_num(record.get(f)) for f in ["open", "high", "low", "close"])
        if None not in (o, h, l, c):
            if h < max(o, c, l):
                errors.append(_issue("STREAM_INVALID_OHLC", "high is below an OHLC component", "error", "high", h, f">= {max(o, c, l)}"))
            if l > min(o, c, h):
                errors.append(_issue("STREAM_INVALID_OHLC", "low is above an OHLC component", "error", "low", l, f"<= {min(o, c, h)}"))
    return _result(errors, warnings)
