from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.features import (
    PERSISTED_INTRADAY_TIMEFRAMES,
    run_intraday_features_with_summary,
)

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DEFAULT_INTRADAY_TIMEFRAMES = PERSISTED_INTRADAY_TIMEFRAMES
LEGACY_INTRADAY_WARNING = (
    "intraday is a legacy feature alias and does not ingest new SSI candles. "
    "It persists only 15m/60m features; use intraday-ingest for 1m source data."
)


def run_intraday_pipeline(
    snapshot_time: str | None = None,
    symbols: list[str] | None = None,
    timeframes: tuple[str, ...] = DEFAULT_INTRADAY_TIMEFRAMES,
) -> dict:
    """Compatibility alias for explicit incremental 15m/60m features."""
    resolved_snapshot = snapshot_time or datetime.now(VN_TZ).isoformat(
        timespec="seconds"
    )
    feature_timeframes = tuple(timeframes or DEFAULT_INTRADAY_TIMEFRAMES)
    feature_symbols = [symbol.upper() for symbol in symbols] if symbols else None
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
