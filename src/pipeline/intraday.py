from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.database.client import SupabaseClient
from src.engine.feature_engine import run_feature_engine

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DEFAULT_INTRADAY_TIMEFRAMES = ("1m", "5m", "15m")


def run_intraday_pipeline(
    snapshot_time: str | None = None,
    symbols: list[str] | None = None,
    timeframes: tuple[str, ...] = DEFAULT_INTRADAY_TIMEFRAMES,
) -> dict:
    """Run the intraday production flow for in-session snapshots.

    Current implementation is intentionally conservative: it does not call the
    daily ingest flow and only computes incremental intraday features from data
    already available in ``stock_intraday``. A real-time SSI fetch step should
    be added here once the snapshot ingest is stable.
    """
    resolved_snapshot = snapshot_time or datetime.now(VN_TZ).isoformat(timespec="seconds")
    feature_timeframes = tuple(timeframes or DEFAULT_INTRADAY_TIMEFRAMES)
    feature_symbols = [s.upper() for s in symbols] if symbols else None

    if "1d" in feature_timeframes:
        raise ValueError("Intraday pipeline must not calculate 1d features; use EOD for 1d.")

    if feature_symbols is None:
        feature_symbols = SupabaseClient().get_symbols()

    print(f"🚀 Intraday snapshot={resolved_snapshot} symbols={feature_symbols or 'ALL'} timeframes={feature_timeframes}")
    print("ℹ️ TODO phase 2: fetch latest in-session SSI intraday candles before feature calculation.")

    feature_records = run_feature_engine(
        symbols=feature_symbols,
        mode="incremental",
        timeframes=feature_timeframes,
    )

    # TODO phase 2:
    # signal_summary = run_signal_engine(...)
    # backtest_stats = lookup_backtest_stats(...)
    # alert_summary = create_intraday_alerts(...)

    return {
        "flow": "intraday",
        "snapshot_time": resolved_snapshot,
        "symbol_count": len(feature_symbols or []),
        "new_candles": 0,
        "feature_records": feature_records,
        "status": "OK",
        "errors": [],
    }
