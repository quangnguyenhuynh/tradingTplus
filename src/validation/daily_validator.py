from __future__ import annotations

from typing import Any

from src.validation.models import ValidationIssue, ValidationResult

PRICE_TOLERANCE = 1e-6
REQUIRED_FIELDS = [
    "symbol", "trading_date", "open_price", "highest_price", "lowest_price",
    "close_price",
]
OPTIONAL_MARKET_FIELDS = ["total_match_vol", "total_match_val", "total_traded_vol", "total_traded_value"]
PRICE_FIELDS = [
    "open_price", "highest_price", "lowest_price", "close_price", "ref_price",
    "ceiling_price", "floor_price", "average_price", "close_price_adjusted",
]
NON_NEGATIVE_FIELDS = [
    "total_match_vol", "total_match_val", "total_deal_vol", "total_deal_val",
    "total_traded_vol", "total_traded_value", "foreign_buy_vol_total",
    "foreign_sell_vol_total", "foreign_buy_val_total", "foreign_sell_val_total",
    "total_buy_trade", "total_buy_trade_vol", "total_sell_trade", "total_sell_trade_vol",
]


def _missing(value: Any) -> bool:
    return value is None or value == ""


def _num(value: Any) -> float | None:
    if _missing(value):
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _issue(code: str, message: str, severity: str, field: str | None = None, actual: Any = None, expected: Any = None) -> ValidationIssue:
    return ValidationIssue(code=code, message=message, severity=severity, field=field, actual_value=actual, expected_value=expected)


def _result(errors: list[ValidationIssue], warnings: list[ValidationIssue]) -> ValidationResult:
    return ValidationResult(is_valid=not errors, errors=errors, warnings=warnings)


def _eq(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance


def validate_daily_record(record: dict) -> ValidationResult:
    if not isinstance(record, dict):
        raise TypeError("daily record must be a dict")
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    for field in REQUIRED_FIELDS:
        if field not in record or _missing(record.get(field)):
            errors.append(_issue("DAILY_REQUIRED_FIELD_MISSING", f"Required field {field} is missing", "error", field, record.get(field), "non-empty value"))
    for field in OPTIONAL_MARKET_FIELDS:
        if field not in record or _missing(record.get(field)):
            warnings.append(_issue("DAILY_OPTIONAL_MARKET_FIELD_MISSING", f"Optional market field {field} is missing", "warning", field, record.get(field), "market value when SSI provides it"))

    has_trading = any((_num(record.get(f)) or 0) > 0 for f in OPTIONAL_MARKET_FIELDS)
    for field in PRICE_FIELDS:
        value = _num(record.get(field))
        if value is None:
            continue
        if value < 0 or (value == 0 and has_trading):
            errors.append(_issue("DAILY_NON_POSITIVE_PRICE", f"Price field {field} must be positive on trading days", "error", field, value, "> 0"))
    for field in NON_NEGATIVE_FIELDS:
        value = _num(record.get(field))
        if value is not None and value < 0:
            errors.append(_issue("DAILY_NEGATIVE_VOLUME_OR_VALUE", f"Volume/value field {field} must not be negative", "error", field, value, ">= 0"))

    o = _num(record.get("open_price")); h = _num(record.get("highest_price")); l = _num(record.get("lowest_price")); c = _num(record.get("close_price"))
    if None not in (o, h, l, c):
        if h < max(o, c, l):
            errors.append(_issue("DAILY_INVALID_OHLC", "highest_price is below an OHLC component", "error", "highest_price", h, f">= {max(o, c, l)}"))
        if l > min(o, c, h):
            errors.append(_issue("DAILY_INVALID_OHLC", "lowest_price is above an OHLC component", "error", "lowest_price", l, f"<= {min(o, c, h)}"))
        if h < l:
            errors.append(_issue("DAILY_INVALID_OHLC", "highest_price is below lowest_price", "error", "highest_price", h, f">= {l}"))

    floor = _num(record.get("floor_price")); ref = _num(record.get("ref_price")); ceiling = _num(record.get("ceiling_price"))
    if None not in (floor, ref, ceiling) and not (floor - PRICE_TOLERANCE <= ref <= ceiling + PRICE_TOLERANCE):
        warnings.append(_issue("DAILY_INVALID_PRICE_BOUNDS", "ref_price is outside floor_price and ceiling_price; this may reflect a corporate action", "warning", "ref_price", ref, f"{floor} <= ref_price <= {ceiling}"))
    if None not in (floor, ceiling):
        ohlc_values = [value for value in (o, h, l, c) if value is not None]
        corporate_action_candidate = len(ohlc_values) == 4 and (
            all(value < floor - PRICE_TOLERANCE for value in ohlc_values)
            or all(value > ceiling + PRICE_TOLERANCE for value in ohlc_values)
        )
        for field in ["open_price", "highest_price", "lowest_price", "close_price"]:
            value = _num(record.get(field))
            if value is not None and not (floor - PRICE_TOLERANCE <= value <= ceiling + PRICE_TOLERANCE):
                issue = _issue(
                    "DAILY_PRICE_OUTSIDE_LIMIT",
                    f"{field} is outside daily price limits" + ("; all OHLC prices are on the same side, which may reflect a corporate action" if corporate_action_candidate else ""),
                    "warning" if corporate_action_candidate else "error",
                    field,
                    value,
                    f"{floor} <= {field} <= {ceiling}",
                )
                (warnings if corporate_action_candidate else errors).append(issue)

    if None not in (c, ref):
        pc = _num(record.get("price_change"))
        if pc is not None:
            expected = c - ref
            tol = max(1e-6, abs(ref) * 0.0001)
            if not _eq(pc, expected, tol):
                warnings.append(_issue("DAILY_PRICE_CHANGE_MISMATCH", "price_change differs from close_price - ref_price", "warning", "price_change", pc, expected))
            pct = _num(record.get("per_price_change"))
            if pct is not None and ref != 0:
                expected_pct = pc / ref * 100
                if not _eq(pct, expected_pct, tol):
                    warnings.append(_issue("DAILY_PERCENT_CHANGE_MISMATCH", "per_price_change differs from price_change / ref_price * 100", "warning", "per_price_change", pct, expected_pct))

    tmv = _num(record.get("total_match_vol")); tdv = _num(record.get("total_deal_vol")); ttv = _num(record.get("total_traded_vol"))
    if None not in (tmv, tdv, ttv) and not _eq(tmv + tdv, ttv, 1e-6):
        warnings.append(_issue("DAILY_TOTAL_VOLUME_MISMATCH", "total_traded_vol differs from match plus deal volume", "warning", "total_traded_vol", ttv, tmv + tdv))
    tmval = _num(record.get("total_match_val")); tdval = _num(record.get("total_deal_val")); ttval = _num(record.get("total_traded_value"))
    if None not in (tmval, tdval, ttval) and not _eq(tmval + tdval, ttval, 1e-6):
        warnings.append(_issue("DAILY_TOTAL_VALUE_MISMATCH", "total_traded_value differs from match plus deal value", "warning", "total_traded_value", ttval, tmval + tdval))

    return _result(errors, warnings)
