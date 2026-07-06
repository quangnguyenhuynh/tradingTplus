"""Shared intraday trade value helpers."""

from __future__ import annotations

import math
from typing import Any


def _is_missing(value: Any) -> bool:
    if value is None or value == "":
        return True
    try:
        return bool(math.isnan(value))
    except (TypeError, ValueError):
        return False


def _to_float(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _to_int(value: Any) -> int | None:
    parsed = _to_float(value)
    if parsed is None:
        return None
    return int(parsed)


def calculate_trade_value(close: Any, volume: Any) -> int | None:
    """Return BIGINT-safe trade value for one normalized intraday candle.

    SSI intraday candles provide per-candle OHLC + volume. They do not provide a
    reliable turnover value, so normalized stock_intraday.value is always
    derived as int(round(close * volume)). Missing/invalid close or volume keeps
    value NULL.
    """
    close_float = _to_float(close)
    volume_int = _to_int(volume)
    if close_float is None or volume_int is None:
        return None
    return int(round(close_float * volume_int))
