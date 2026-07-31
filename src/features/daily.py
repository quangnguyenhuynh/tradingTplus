"""Daily feature calculation and stock_daily-only execution."""

from __future__ import annotations

import pandas as pd

from src.database.client import SupabaseClient

from .common import _add_common_features
from .runtime import (
    filter_output_by_time,
    fetch_stock_daily_rows,
    fetch_feature_watermark,
    log_feature_run,
    normalize_target_date,
    run_source_summary,
    target_utc_bounds,
    upsert_feature_frame,
)


def _daily_to_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    required = [
        "trading_date",
        "open_price",
        "highest_price",
        "lowest_price",
        "close_price",
    ]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns for daily feature calculation: {missing}"
        )

    out = pd.DataFrame(
        {
            "time": (
                pd.to_datetime(df["trading_date"], errors="coerce")
                .dt.tz_localize("Asia/Ho_Chi_Minh")
                .dt.tz_convert("UTC")
            ),
            "open": pd.to_numeric(df["open_price"], errors="coerce"),
            "high": pd.to_numeric(df["highest_price"], errors="coerce"),
            "low": pd.to_numeric(df["lowest_price"], errors="coerce"),
            "close": pd.to_numeric(df["close_price"], errors="coerce"),
            "volume": pd.to_numeric(
                df.get("total_traded_vol", df.get("total_match_vol")),
                errors="coerce",
            ),
            "value": pd.to_numeric(
                df.get("total_traded_value", df.get("total_match_val")),
                errors="coerce",
            ),
        }
    )
    return (
        out.dropna(subset=["time"])
        .sort_values("time")
        .drop_duplicates(subset=["time"], keep="last")
        .reset_index(drop=True)
    )


def compute_daily_features(daily_df: pd.DataFrame) -> pd.DataFrame:
    if daily_df.empty:
        return pd.DataFrame()

    out = _daily_to_ohlcv(daily_df)
    date_key = out["time"].dt.tz_convert("Asia/Ho_Chi_Minh").dt.date
    out["return_1m"] = pd.NA
    out["return_5m"] = pd.NA
    out["return_15m"] = pd.NA
    out = _add_common_features(
        out,
        date_key,
        daily_df,
        reset_volume_by_day=False,
    )
    out["vwap_intraday"] = pd.NA
    out["close_above_vwap"] = pd.NA
    out["distance_to_vwap_pct"] = pd.NA
    return out


def calculate_daily_features_for_symbol(
    symbol,
    mode="full",
    target_date=None,
    upsert_batch_size=1000,
    records_by_timeframe=None,
):
    """Read only stock_daily and write canonical 1d feature rows."""
    db = SupabaseClient()
    target = normalize_target_date(target_date) if mode == "incremental" else None
    watermark = fetch_feature_watermark(db, symbol, "1d") if target else None
    start_date = None
    if target is not None:
        anchor = watermark or pd.Timestamp(target, tz="UTC")
        start_date = (anchor - pd.DateOffset(years=5)).date()
    rows = fetch_stock_daily_rows(
        db, symbol, start_date=start_date, end_date=target
    )
    if not rows:
        return 0

    frame = compute_daily_features(pd.DataFrame(rows))
    if target is not None:
        start, end, _ = target_utc_bounds(target)
        if watermark is not None:
            start = watermark + pd.Timedelta(nanoseconds=1)
        frame = filter_output_by_time(frame, start, end)
    count = upsert_feature_frame(
        db,
        symbol,
        "1d",
        frame,
        upsert_batch_size,
    )
    if records_by_timeframe is not None:
        records_by_timeframe["1d"] = (
            records_by_timeframe.get("1d", 0) + count
        )
    log_feature_run(
        symbol,
        "1d",
        mode,
        len(rows),
        len(frame),
        count,
        frame,
    )
    return count


def run_daily_features_with_summary(
    symbols=None,
    mode="incremental",
    target_date=None,
):
    return run_source_summary(
        "features-daily",
        symbols,
        mode,
        target_date,
        ("1d",),
        calculate_daily_features_for_symbol,
    )
