"""Pure, allow-listed transforms used by source mappings."""
from __future__ import annotations

import math
import re
from datetime import date, datetime, time
from typing import Any, Callable
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UTC_TZ = ZoneInfo("UTC")
_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,19}$")

class TransformError(ValueError):
    """A present source value cannot be normalized."""

def _reject_bool(value: Any) -> None:
    if isinstance(value, bool):
        raise TransformError("boolean is not a number")

def to_float(value: Any, _context: dict[str, Any]) -> float:
    _reject_bool(value)
    try: result = float(value)
    except (TypeError, ValueError) as exc: raise TransformError("expected finite number") from exc
    if not math.isfinite(result): raise TransformError("expected finite number")
    return result

def to_int(value: Any, context: dict[str, Any]) -> int:
    number = to_float(value, context)
    if not number.is_integer(): raise TransformError("expected integer")
    return int(number)

def to_text(value: Any, _context: dict[str, Any]) -> str:
    if isinstance(value, (dict, list, tuple, set, bool)): raise TransformError("expected text")
    result = str(value).strip()
    if not result: raise TransformError("expected non-empty text")
    return result

def to_symbol(value: Any, context: dict[str, Any]) -> str:
    result = to_text(value, context).upper()
    if not _SYMBOL.fullmatch(result): raise TransformError("invalid symbol")
    return result

def to_date(value: Any, _context: dict[str, Any]) -> str:
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try: return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError: pass
    raise TransformError("invalid trading date")

def context_date(value: Any, context: dict[str, Any]) -> str:
    return to_date(value, context)

def candle_timestamp(value: Any, context: dict[str, Any]) -> str:
    try:
        base = datetime.strptime(str(context["date"]), "%d/%m/%Y").date()
        hour, minute, second = map(int, str(value).split(":"))
        local = datetime.combine(base, time(hour, minute, second), tzinfo=VN_TZ)
    except (KeyError, TypeError, ValueError) as exc: raise TransformError("invalid candle timestamp") from exc
    return local.astimezone(UTC_TZ).strftime("%Y-%m-%dT%H:%M:%SZ")

def market_timestamp(value: Any, context: dict[str, Any]) -> str:
    """Normalize a v3 timestamp without ever inventing its calendar date."""
    text = str(value).strip()
    parsed = None
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            parsed = datetime.fromisoformat(candidate)
            break
        except ValueError:
            pass
    if parsed is None:
        for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                pass
    if parsed is None:
        raise TransformError("invalid timestamp with no source date")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=VN_TZ)
    expected = context.get("date")
    if expected and parsed.astimezone(VN_TZ).date() != datetime.strptime(expected, "%d/%m/%Y").date():
        raise TransformError("timestamp is outside requested Vietnam trading date")
    return parsed.astimezone(UTC_TZ).strftime("%Y-%m-%dT%H:%M:%SZ")

def zero_price_to_null(value: Any, context: dict[str, Any]) -> float | None:
    number = to_float(value, context)
    return None if number == 0 else number

TRANSFORMS: dict[str, Callable[[Any, dict[str, Any]], Any]] = {
    "float": to_float, "int": to_int, "text": to_text, "symbol": to_symbol,
    "date": to_date, "context_date": context_date, "candle_timestamp": candle_timestamp,
    "market_timestamp": market_timestamp,
}


def intraday_timestamp(value: Any, context: dict[str, Any]) -> str:
    """Generic normalization accepts only a full source datetime with explicit timezone.

    Source-specific market-local formats use a separate allow-listed transform.
    Never combine a time-only value with the request date.
    """
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value.strip()
    ):
        raise TransformError("UNVERIFIED_TIMESTAMP: require full source date/time with explicit timezone")
    try:
        parsed = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    except ValueError as exc:
        raise TransformError('invalid source datetime') from exc
    local_date = parsed.astimezone(VN_TZ).date().isoformat()
    start, end = context.get('from_date'), context.get('to_date')
    if start and local_date < start or end and local_date > end:
        raise TransformError('source timestamp is outside requested Vietnam date range')
    return parsed.astimezone(UTC_TZ).isoformat().replace('+00:00', 'Z')


TRANSFORMS['intraday_timestamp'] = intraday_timestamp


def intraday_volume(value: Any, _context: dict[str, Any]) -> int:
    """Exact, finite integral share count within the unchanged BIGINT contract."""
    from decimal import Decimal, InvalidOperation

    _reject_bool(value)
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise TransformError('expected finite integral volume') from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise TransformError('expected finite integral volume')
    if not 0 <= number <= 2**63 - 1:
        raise TransformError('volume is outside nonnegative BIGINT range')
    return int(number)


TRANSFORMS['intraday_volume'] = intraday_volume


def ssi_v3_intraday_timestamp(value: Any, context: dict[str, Any]) -> str:
    """Observed SSI v3 tradingDate is market-local; other naive forms stay rejected.

    This transform is referenced only by the SSI v3 stock_intraday mapping.
    The timezone interpretation does not establish bar-start/end semantics.
    """
    if isinstance(value, str) and re.fullmatch(
        r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}(?:\.\d{1,6})?', value.strip()
    ):
        # The caller identifies which alias was used; only tradingDate has
        # observed evidence for market-local (timezone-less) timestamps.
        source_field = context.get('mapping_source_field', 'ohlc.tradingDate')
        if source_field.casefold() != 'ohlc.tradingdate':
            raise TransformError('UNVERIFIED_TIMESTAMP: legacy time alias requires an explicit timezone')
        text = value.strip()
        try:
            parsed = datetime.strptime(text, '%Y/%m/%d %H:%M:%S.%f' if '.' in text else '%Y/%m/%d %H:%M:%S')
        except ValueError as exc:
            raise TransformError('invalid SSI v3 tradingDate datetime') from exc
        value = parsed.replace(tzinfo=VN_TZ).isoformat()
    return intraday_timestamp(value, context)


def intraday_source_value(value: Any, _context: dict[str, Any]) -> int:
    """Exact SSI-reported value, never through float, within nullable BIGINT contract."""
    from decimal import Decimal, InvalidOperation

    if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
        raise TransformError('source value must be an exact decimal string or integer, not float/bool')
    text = str(value).strip()
    if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', text):
        raise TransformError('source value must be finite and integral')
    try:
        number = Decimal(text)
        if not number.is_finite() or number != number.to_integral_value():
            raise TransformError('source value must be finite and integral')
        if not 0 <= number <= 2**63 - 1:
            raise TransformError('source value is outside nonnegative signed BIGINT range')
    except InvalidOperation as exc:
        raise TransformError('source value must be finite and integral') from exc
    return int(number)


TRANSFORMS['ssi_v3_intraday_timestamp'] = ssi_v3_intraday_timestamp
TRANSFORMS['intraday_source_value'] = intraday_source_value
