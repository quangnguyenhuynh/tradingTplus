from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.features import run_intraday_features_with_summary

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DEFAULT_INTRADAY_TIMEFRAMES = ("1m", "5m", "15m")
LEGACY_INTRADAY_WARNING = "intraday is a legacy feature alias and does not ingest new SSI candles. Use the explicit features command."


def run_intraday_pipeline(
    snapshot_time: str | None = None,
    symbols: list[str] | None = None,
    timeframes: tuple[str, ...] = DEFAULT_INTRADAY_TIMEFRAMES,
) -> dict:
    """Compatibility alias for explicit incremental feature calculation."""
    resolved_snapshot = snapshot_time or datetime.now(VN_TZ).isoformat(timespec="seconds")
    feature_timeframes = tuple(timeframes or DEFAULT_INTRADAY_TIMEFRAMES)
    if "1d" in feature_timeframes:
        raise ValueError("Legacy intraday alias must not calculate 1d features; use `features --timeframes 1d`.")
    feature_symbols = [s.upper() for s in symbols] if symbols else None
    print(f"⚠️ {LEGACY_INTRADAY_WARNING}")
    summary = run_intraday_features_with_summary(
        symbols=feature_symbols,
        mode="incremental",
        timeframes=feature_timeframes,
    )
    return {
        **summary,
        "flow": "intraday",
        "snapshot_time": resolved_snapshot,
        "legacy_warning": LEGACY_INTRADAY_WARNING,
    }
