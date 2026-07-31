"""Intraday aggregation, calculation, closed-bucket filtering, and execution."""

from __future__ import annotations

import logging
from datetime import date, datetime

import pandas as pd

from src.database.client import SupabaseClient

from .common import (
    INTRADAY_TIMEFRAMES,
    _add_common_features,
    _prepare_ohlcv,
    nullable_comparison,
    safe_div,
)
from .runtime import (
    VN_TZ,
    date_bounds_for_daily_context,
    fetch_stock_daily_rows,
    fetch_feature_watermark,
    fetch_intraday_trading_session_window,
    fetch_stock_intraday_paginated,
    filter_output_by_time,
    log_feature_run,
    normalize_target_date,
    normalize_timeframes,
    run_source_summary,
    target_utc_bounds,
    upsert_feature_frame,
)

logger = logging.getLogger(__name__)

RETURN_TOLERANCE_MINUTES = {1: 1, 5: 2, 15: 2}


def aggregate_timeframe(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Aggregate canonical 1m rows without crossing VN dates or lunch."""
    if timeframe not in INTRADAY_TIMEFRAMES:
        raise ValueError(
            f"Unsupported intraday timeframe: {timeframe}. "
            f"Supported: {sorted(INTRADAY_TIMEFRAMES)}"
        )
    if df.empty:
        return df.copy()

    out = _prepare_ohlcv(df)
    if timeframe == "1m":
        return out

    rule = {"5m": "5min", "15m": "15min", "60m": "60min"}[timeframe]
    local = out.copy()
    local["time"] = local["time"].dt.tz_convert("Asia/Ho_Chi_Minh")
    local = local.set_index("time")
    pieces = []
    for (_trading_date, _session), part in local.groupby(
        [local.index.date, (local.index.hour >= 12)],
        sort=True,
    ):
        pieces.append(
            part.resample(rule, label="left", closed="left")
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                    "value": "sum",
                }
            )
            .dropna(subset=["open", "high", "low", "close"])
            .reset_index()
        )
    if not pieces:
        return out.iloc[0:0].reset_index(drop=True)

    result = pd.concat(pieces, ignore_index=True)
    result["time"] = pd.to_datetime(result["time"]).dt.tz_convert("UTC")
    return result.sort_values("time").reset_index(drop=True)


def _time_aware_return(
    out: pd.DataFrame,
    horizon_minutes: int,
) -> pd.Series:
    """Use the latest same-session candle at/before the wall-clock target."""
    tolerance = pd.Timedelta(
        minutes=RETURN_TOLERANCE_MINUTES[horizon_minutes]
    )
    target_delta = pd.Timedelta(minutes=horizon_minutes)
    local_time = out["time"].dt.tz_convert("Asia/Ho_Chi_Minh")
    date_keys = local_time.dt.date
    session_keys = (local_time.dt.hour >= 12).astype(int)
    result = pd.Series(float("nan"), index=out.index, dtype="float64")

    for indexes in out.groupby(
        [date_keys, session_keys],
        sort=False,
    ).groups.values():
        positions = list(indexes)
        times = out.loc[positions, "time"].reset_index(drop=True)
        closes = out.loc[positions, "close"].reset_index(drop=True)
        targets = times - target_delta
        reference_positions = times.searchsorted(targets, side="right") - 1
        valid = reference_positions >= 0
        if not valid.any():
            continue

        candidate_rows = reference_positions[valid]
        candidate_times = times.iloc[candidate_rows].reset_index(drop=True)
        valid_targets = targets[valid].reset_index(drop=True)
        within_tolerance = (valid_targets - candidate_times) <= tolerance
        output_positions = (
            pd.Series(positions)[valid]
            .reset_index(drop=True)[within_tolerance]
        )
        reference_closes = (
            closes.iloc[candidate_rows]
            .reset_index(drop=True)[within_tolerance]
        )
        current_closes = (
            closes[pd.Series(valid).to_numpy()]
            .reset_index(drop=True)[within_tolerance]
        )
        result.loc[output_positions.to_list()] = (
            current_closes.to_numpy() / reference_closes.to_numpy() - 1
        )
    return result


def compute_intraday_features(
    df: pd.DataFrame,
    timeframe: str,
    daily_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if timeframe not in INTRADAY_TIMEFRAMES:
        raise ValueError(f"Unsupported intraday timeframe: {timeframe}")
    if df.empty:
        return df.copy()

    out = _prepare_ohlcv(df)
    if out["time"].duplicated().any():
        raise ValueError("Duplicate time detected in feature input")
    date_key = out["time"].dt.tz_convert("Asia/Ho_Chi_Minh").dt.date
    out["return_1m"] = (
        _time_aware_return(out, 1) if timeframe == "1m" else pd.NA
    )
    out["return_5m"] = (
        _time_aware_return(out, 5)
        if timeframe in {"1m", "5m"}
        else pd.NA
    )
    out["return_15m"] = (
        _time_aware_return(out, 15)
        if timeframe in {"1m", "5m", "15m"}
        else pd.NA
    )
    out = _add_common_features(
        out,
        date_key,
        daily_df,
        reset_volume_by_day=True,
    )
    cumulative_value = out.groupby(date_key)["value"].cumsum()
    cumulative_volume = out.groupby(date_key)["volume"].cumsum()
    out["vwap_intraday"] = safe_div(
        cumulative_value,
        cumulative_volume,
        out.index,
    )
    out["close_above_vwap"] = nullable_comparison(
        out["close"],
        out["vwap_intraday"],
        lambda left, right: left > right,
    )
    out["distance_to_vwap_pct"] = safe_div(
        out["close"] - out["vwap_intraday"],
        out["vwap_intraday"],
        out.index,
    )
    return out


def _resolve_as_of(target: date, as_of=None) -> pd.Timestamp:
    now = pd.Timestamp.now(tz=VN_TZ)
    if as_of is None:
        if target < now.date():
            return pd.Timestamp(
                datetime.combine(
                    target,
                    datetime.max.time(),
                    tzinfo=VN_TZ,
                )
            )
        if target > now.date():
            raise ValueError("target date cannot be in the future")
        return now

    text = str(as_of).strip()
    if ":" in text and "T" not in text and " " not in text:
        try:
            parsed_time = datetime.strptime(text, "%H:%M").time()
        except ValueError as exc:
            raise ValueError(
                "as_of HH:MM must be valid Vietnam local time"
            ) from exc
        stamp = pd.Timestamp(
            datetime.combine(target, parsed_time, tzinfo=VN_TZ)
        )
    else:
        stamp = pd.Timestamp(text)
        if stamp.tzinfo is None:
            raise ValueError("full as_of timestamp must be timezone-aware")
        stamp = stamp.tz_convert(VN_TZ)
        if stamp.date() != target:
            raise ValueError("as_of timestamp must fall on target date")
    if stamp > now:
        raise ValueError("as_of cannot be in the future")
    return stamp


def _bucket_close_local(
    start: pd.Timestamp,
    timeframe: str,
) -> pd.Timestamp:
    minutes = int(timeframe[:-1])
    normal_close = start + pd.Timedelta(minutes=minutes)
    local_date = start.date()
    morning_end = pd.Timestamp(
        datetime.combine(
            local_date,
            datetime.strptime("11:30", "%H:%M").time(),
            tzinfo=VN_TZ,
        )
    )
    afternoon_end = pd.Timestamp(
        datetime.combine(
            local_date,
            datetime.strptime("15:00", "%H:%M").time(),
            tzinfo=VN_TZ,
        )
    )
    session_end = morning_end if start < morning_end else afternoon_end
    return min(normal_close, session_end)


def filter_closed_buckets(
    df: pd.DataFrame,
    timeframe: str,
    as_of: pd.Timestamp,
) -> pd.DataFrame:
    """Keep observed buckets whose configured VN-session close has passed."""
    if df.empty:
        return df.copy()
    starts = pd.to_datetime(df["time"], utc=True).dt.tz_convert(VN_TZ)
    closed = starts.map(
        lambda start: _bucket_close_local(start, timeframe) <= as_of
    )
    return df.loc[closed.to_numpy()].reset_index(drop=True)


def calculate_intraday_features_for_symbol(
    symbol,
    timeframes=None,
    mode="full",
    target_date=None,
    as_of=None,
    upsert_batch_size=1000,
    records_by_timeframe=None,
    warmup_sessions=250,
):
    """Read canonical 1m data and write closed intraday feature rows."""
    normalized = normalize_timeframes(
        timeframes or tuple(INTRADAY_TIMEFRAMES)
    )
    if "1d" in normalized:
        raise ValueError("Intraday feature flow does not accept 1d")

    db = SupabaseClient()
    target = normalize_target_date(target_date) if mode == "incremental" else None
    end = None
    filter_start = None
    filter_end = None
    if target is not None:
        filter_start, filter_end, _ = target_utc_bounds(target)
        end = filter_end.strftime("%Y-%m-%dT%H:%M:%SZ")

    watermarks = {
        timeframe: fetch_feature_watermark(db, symbol, timeframe)
        for timeframe in normalized
    } if target is not None else {timeframe: None for timeframe in normalized}
    rows = (
        fetch_intraday_trading_session_window(
            db, symbol, end, trading_sessions=warmup_sessions
        )
        if target is not None
        else fetch_stock_intraday_paginated(db, symbol, order_desc=False)
    )
    if not rows:
        return 0

    bounds = date_bounds_for_daily_context(rows)
    daily_rows = (
        fetch_stock_daily_rows(db, symbol, bounds[0], bounds[1])
        if bounds
        else []
    )
    latest_local_date = (
        pd.to_datetime(rows[-1]["time"], utc=True)
        .tz_convert(VN_TZ)
        .date()
    )
    cutoff = _resolve_as_of(target or latest_local_date, as_of)
    source = pd.DataFrame(rows)
    observed_dates = (
        pd.to_datetime(source["time"], utc=True)
        .dt.tz_convert(VN_TZ)
        .dt.date.nunique()
    )

    total = 0
    for timeframe in normalized:
        aggregated = aggregate_timeframe(source, timeframe)
        closed = filter_closed_buckets(aggregated, timeframe, cutoff)
        computed = (
            compute_intraday_features(
                closed,
                timeframe,
                pd.DataFrame(daily_rows),
            )
            if not closed.empty
            else closed
        )
        output = filter_output_by_time(
            computed,
            (
                watermarks[timeframe] + pd.Timedelta(nanoseconds=1)
                if watermarks[timeframe] is not None
                else filter_start
            ),
            filter_end,
        )
        count = upsert_feature_frame(
            db,
            symbol,
            timeframe,
            output,
            upsert_batch_size,
        )
        total += count
        if records_by_timeframe is not None:
            records_by_timeframe[timeframe] = (
                records_by_timeframe.get(timeframe, 0) + count
            )
        logger.info(
            "Intraday warm-up symbol=%s timeframe=%s source_range=%s..%s "
            "aggregated=%s prior_dates=%s sufficient=%s",
            symbol,
            timeframe,
            source["time"].min(),
            source["time"].max(),
            len(aggregated),
            observed_dates,
            len(aggregated) >= 50 and observed_dates >= 21,
        )
        log_feature_run(
            symbol,
            timeframe,
            mode,
            len(rows),
            len(computed),
            count,
            output,
        )
    return total


def run_intraday_features_with_summary(
    symbols=None,
    mode="incremental",
    timeframes=None,
    target_date=None,
    as_of=None,
):
    normalized = normalize_timeframes(
        timeframes or ("1m", "5m", "15m", "60m")
    )
    if "1d" in normalized:
        raise ValueError(
            "features-intraday accepts only 1m, 5m, 15m, and 60m"
        )
    return run_source_summary(
        "features-intraday",
        symbols,
        mode,
        target_date,
        normalized,
        calculate_intraday_features_for_symbol,
        as_of,
    )
