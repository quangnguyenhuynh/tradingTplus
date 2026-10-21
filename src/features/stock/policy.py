"""Production persistence policy for feature timeframes.

Clean 1-minute candles remain the canonical intraday source. Production feature
persistence is intentionally limited to 15m, 60m, and 1d for the T+3/T+5
product horizon. The lower-level calculators may still be used in tests or
research, but public production runners reject 1m and 5m feature writes.
"""

from __future__ import annotations

from .daily import run_daily_features_with_summary
from .intraday import run_intraday_features_with_summary as _run_intraday_features
from .runner import run_feature_engine_with_summary as _run_mixed_features

PERSISTED_DAILY_TIMEFRAMES = ("1d",)
PERSISTED_INTRADAY_TIMEFRAMES = ("15m", "60m")
DEFAULT_PERSISTED_FEATURE_TIMEFRAMES = ("15m", "60m", "1d")
PERSISTED_FEATURE_TIMEFRAMES = frozenset(DEFAULT_PERSISTED_FEATURE_TIMEFRAMES)


def validate_persisted_timeframes(timeframes) -> tuple[str, ...]:
    if timeframes is None:
        return DEFAULT_PERSISTED_FEATURE_TIMEFRAMES
    if isinstance(timeframes, str):
        timeframes = [timeframes]
    normalized = tuple(dict.fromkeys(str(value).strip() for value in timeframes))
    unsupported = sorted(set(normalized) - PERSISTED_FEATURE_TIMEFRAMES)
    if unsupported:
        raise ValueError(
            "Feature persistence supports only 1d, 15m, and 60m. "
            f"Unsupported timeframe(s): {unsupported}. "
            "Keep stock_intraday 1m as the canonical source; do not persist "
            "features for 1m or 5m."
        )
    return normalized


def validate_intraday_persisted_timeframes(timeframes) -> tuple[str, ...]:
    normalized = (
        PERSISTED_INTRADAY_TIMEFRAMES
        if timeframes is None
        else validate_persisted_timeframes(timeframes)
    )
    invalid = sorted(set(normalized) - set(PERSISTED_INTRADAY_TIMEFRAMES))
    if invalid:
        raise ValueError(
            "features-intraday accepts only persisted timeframes 15m and 60m; "
            f"got {invalid}."
        )
    return normalized


def run_intraday_features_with_summary(
    symbols=None,
    mode="incremental",
    timeframes=None,
    target_date=None,
    as_of=None,
):
    normalized = validate_intraday_persisted_timeframes(timeframes)
    return _run_intraday_features(
        symbols=symbols,
        mode=mode,
        timeframes=normalized,
        target_date=target_date,
        as_of=as_of,
    )


def run_feature_engine_with_summary(
    symbols=None,
    mode="full",
    timeframes=None,
    target_date=None,
    as_of=None,
):
    normalized = validate_persisted_timeframes(timeframes)
    return _run_mixed_features(
        symbols=symbols,
        mode=mode,
        timeframes=normalized,
        target_date=target_date,
        as_of=as_of,
    )


def run_feature_engine(
    symbols=None,
    mode="full",
    timeframes=None,
    target_date=None,
):
    return run_feature_engine_with_summary(
        symbols=symbols,
        mode=mode,
        timeframes=timeframes,
        target_date=target_date,
    )["total_records"]


__all__ = [
    "DEFAULT_PERSISTED_FEATURE_TIMEFRAMES",
    "PERSISTED_DAILY_TIMEFRAMES",
    "PERSISTED_FEATURE_TIMEFRAMES",
    "PERSISTED_INTRADAY_TIMEFRAMES",
    "run_daily_features_with_summary",
    "run_feature_engine",
    "run_feature_engine_with_summary",
    "run_intraday_features_with_summary",
    "validate_intraday_persisted_timeframes",
    "validate_persisted_timeframes",
]
