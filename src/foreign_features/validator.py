"""Strict source validation without source repair."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

VALUE_FIELDS = ("foreign_buy_val_total", "foreign_sell_val_total", "net_foreign_val", "total_traded_value")
VOLUME_FIELDS = ("foreign_buy_vol_total", "foreign_sell_vol_total", "net_foreign_vol")


def decimal_value(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not numeric")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid numeric value") from exc
    if not result.is_finite():
        raise ValueError("numeric value must be finite")
    return result


def validate_source_row(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    symbol = row.get("symbol")
    try:
        date.fromisoformat(str(row.get("trading_date")))
    except ValueError:
        reasons.append("INVALID_DATE")
    if not isinstance(symbol, str) or not symbol.strip():
        reasons.append("INVALID_SYMBOL")
    values: dict[str, Decimal | None] = {}
    for field in (*VALUE_FIELDS, *VOLUME_FIELDS):
        try:
            values[field] = decimal_value(row.get(field))
        except ValueError:
            values[field] = None
            reasons.append(f"INVALID_{field.upper()}")
    for field in ("foreign_buy_val_total", "foreign_sell_val_total", "total_traded_value", "foreign_buy_vol_total", "foreign_sell_vol_total"):
        if values[field] is not None and values[field] < 0:
            reasons.append(f"NEGATIVE_{field.upper()}")
    b, s, n = (values[field] for field in VALUE_FIELDS[:3])
    if None not in (b, s, n) and n != b - s:
        reasons.append("NET_VALUE_MISMATCH")
    bv, sv, nv = (values[field] for field in VOLUME_FIELDS)
    if None not in (bv, sv, nv) and nv != bv - sv:
        reasons.append("NET_VOLUME_MISMATCH")
    turnover = values["total_traded_value"]
    if b is not None and s is not None and turnover == 0 and b + s > 0:
        reasons.append("FOREIGN_ACTIVITY_WITH_ZERO_TURNOVER")
    return reasons
