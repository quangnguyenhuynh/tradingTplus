"""Shared database/runtime plumbing for source-specific feature flows."""

from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.database.client import SupabaseClient
from src.utils.time_utils import app_now_iso

from .common import FEATURE_COLUMNS, SUPPORTED_TIMEFRAMES

logger = logging.getLogger(__name__)

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UTC_TZ = ZoneInfo("UTC")
SOURCE_TIMEFRAME = "1m"
DEFAULT_FEATURE_TIMEFRAMES = ("1m", "5m", "15m", "60m", "1d")
BIGINT_FEATURE_COLUMNS = frozenset({"volume", "value"})


def _serialize_bigint_feature(
    value,
    column: str,
    symbol: str,
    timeframe: str,
    time,
) -> int | None:
    if value is None or value is pd.NA or value is pd.NaT or pd.isna(value):
        return None
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(
            f"Invalid bigint feature column={column} value={value!r} "
            f"symbol={symbol} timeframe={timeframe} time={time}"
        )
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        numeric = float(value)
        if np.isfinite(numeric) and numeric.is_integer():
            return int(numeric)
    raise ValueError(
        f"Invalid bigint feature column={column} value={value!r} "
        f"symbol={symbol} timeframe={timeframe} time={time}"
    )


def normalize_target_date(target_date=None) -> date:
    if target_date is None:
        return datetime.now(VN_TZ).date()
    if isinstance(target_date, datetime):
        return target_date.astimezone(VN_TZ).date() if target_date.tzinfo else target_date.date()
    if isinstance(target_date, date):
        return target_date

    text = str(target_date).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(
        f"target_date must be date, YYYY-MM-DD, or DD/MM/YYYY; got {target_date!r}"
    )


def target_utc_bounds(target_date=None) -> tuple[pd.Timestamp, pd.Timestamp, date]:
    target = normalize_target_date(target_date)
    start_vn = datetime.combine(target, datetime.min.time(), tzinfo=VN_TZ)
    end_vn = start_vn + pd.Timedelta(days=1)
    return (
        pd.Timestamp(start_vn.astimezone(UTC_TZ)),
        pd.Timestamp(end_vn.astimezone(UTC_TZ)),
        target,
    )


def build_feature_records(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
) -> list[dict]:
    if df.empty:
        return []

    out = df[["time"] + FEATURE_COLUMNS].copy()
    out.insert(0, "symbol", symbol)
    out.insert(1, "timeframe", timeframe)
    out["time"] = pd.to_datetime(out["time"], utc=True, errors="coerce")

    float_cols = [
        "open",
        "high",
        "low",
        "close",
        "return_1m",
        "return_5m",
        "return_15m",
        "return_from_open",
        "return_from_prev_close",
        "ema9",
        "ema20",
        "ema50",
        "rsi14",
        "macd",
        "macd_signal",
        "macd_histogram",
        "volume_ma20",
        "volume_ratio",
        "value_ma20",
        "value_ratio",
        "high_20_bars",
        "low_20_bars",
        "vwap_intraday",
        "distance_to_vwap_pct",
        "candle_range",
        "candle_body",
        "candle_body_pct",
        "close_position_in_candle",
    ]
    out[float_cols] = out[float_cols].round(6)
    out[float_cols] = out[float_cols].replace(
        [float("inf"), float("-inf")],
        pd.NA,
    )
    out["last_updated_at"] = app_now_iso()
    out = out.where(pd.notna(out), None)

    records: list[dict] = []
    for row in out.to_dict("records"):
        clean_row = {}
        for key, value in row.items():
            if key in BIGINT_FEATURE_COLUMNS:
                clean_row[key] = _serialize_bigint_feature(
                    value,
                    key,
                    symbol,
                    timeframe,
                    row.get("time"),
                )
            elif value is pd.NA or value is pd.NaT:
                clean_row[key] = None
            elif isinstance(value, (float, np.floating)):
                numeric = float(value)
                clean_row[key] = (
                    None if np.isnan(numeric) or np.isinf(numeric) else numeric
                )
            elif isinstance(value, (int, np.integer)):
                clean_row[key] = int(value)
            elif isinstance(value, pd.Timestamp):
                clean_row[key] = (
                    None
                    if pd.isna(value)
                    else value.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
                )
            elif isinstance(value, datetime):
                stamp = pd.Timestamp(value)
                if stamp.tzinfo is None:
                    stamp = stamp.tz_localize("UTC")
                clean_row[key] = stamp.tz_convert("UTC").strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            else:
                clean_row[key] = value
        records.append(clean_row)
    return records


def fetch_stock_daily_rows(
    db: SupabaseClient,
    symbol: str,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    order_desc: bool = False,
    limit_total: int | None = None,
) -> list[dict]:
    query = (
        db.get()
        .table("stock_daily")
        .select(
            "trading_date, open_price, highest_price, lowest_price, close_price, "
            "total_traded_vol, total_traded_value, total_match_vol, total_match_val"
        )
        .eq("symbol", symbol)
        .order("trading_date", desc=order_desc)
    )
    if start_date is not None:
        query = query.gte("trading_date", str(start_date))
    if end_date is not None:
        query = query.lte("trading_date", str(end_date))
    if limit_total is not None:
        query = query.range(0, limit_total - 1)

    result = db._with_retry(
        lambda current_query=query: current_query.execute(),
        action_name=f"fetch stock_daily {symbol}",
    )
    rows = result.data or []
    return list(reversed(rows)) if order_desc else rows


def date_bounds_for_daily_context(
    rows: list[dict],
) -> tuple[date, date] | None:
    if not rows:
        return None
    times = pd.to_datetime(
        [row.get("time") for row in rows],
        errors="coerce",
        utc=True,
    )
    times = pd.Series(times).dropna()
    if times.empty:
        return None
    local_dates = times.dt.tz_convert(VN_TZ).dt.date
    return local_dates.min() - pd.Timedelta(days=14), local_dates.max()


def fetch_stock_intraday_paginated(
    db: SupabaseClient,
    symbol: str,
    gte_time: str | None = None,
    lt_time: str | None = None,
    order_desc: bool = False,
    page_size: int = 1000,
    limit_total: int | None = None,
) -> list[dict]:
    offset = 0
    rows_all: list[dict] = []

    while True:
        query = (
            db.get()
            .table("stock_intraday")
            .select("time, open, high, low, close, volume, value")
            .eq("symbol", symbol)
            .eq("timeframe", SOURCE_TIMEFRAME)
        )
        if gte_time is not None:
            query = query.gte("time", gte_time)
        if lt_time is not None:
            query = query.lt("time", lt_time)
        query = query.order("time", desc=order_desc).range(
            offset,
            offset + page_size - 1,
        )
        result = db._with_retry(
            lambda current_query=query: current_query.execute(),
            action_name=f"fetch stock_intraday paginated {symbol} offset={offset}",
        )
        page_rows = result.data or []
        if not page_rows:
            break

        rows_all.extend(page_rows)
        if limit_total is not None and len(rows_all) >= limit_total:
            return rows_all[:limit_total]
        if len(page_rows) < page_size:
            break
        offset += page_size

    return rows_all


def fetch_feature_watermark(
    db: SupabaseClient,
    symbol: str,
    timeframe: str,
) -> pd.Timestamp | None:
    """Return the newest persisted feature time for one exact feature stream."""
    query = (
        db.get()
        .table("features")
        .select("time")
        .eq("symbol", symbol)
        .eq("timeframe", timeframe)
        .order("time", desc=True)
        .range(0, 0)
    )
    result = db._with_retry(
        lambda current_query=query: current_query.execute(),
        action_name=f"fetch feature watermark {symbol} {timeframe}",
    )
    rows = result.data or []
    if not rows:
        return None
    value = pd.to_datetime(rows[0].get("time"), errors="coerce", utc=True)
    if pd.isna(value):
        raise ValueError(
            f"Invalid feature watermark symbol={symbol} timeframe={timeframe}"
        )
    return value


def fetch_intraday_trading_session_window(
    db: SupabaseClient,
    symbol: str,
    lt_time: str,
    trading_sessions: int = 250,
    page_size: int = 1000,
) -> list[dict]:
    """Fetch newest 1m rows through at most N observed VN trading dates."""
    if not 200 <= trading_sessions <= 250:
        raise ValueError("intraday warm-up must be between 200 and 250 sessions")
    offset = 0
    rows: list[dict] = []
    observed: list[date] = []
    while len(observed) < trading_sessions:
        query = (
            db.get().table("stock_intraday")
            .select("time, open, high, low, close, volume, value")
            .eq("symbol", symbol).eq("timeframe", SOURCE_TIMEFRAME)
            .lt("time", lt_time).order("time", desc=True)
            .range(offset, offset + page_size - 1)
        )
        result = db._with_retry(
            lambda current_query=query: current_query.execute(),
            action_name=f"fetch intraday warm-up {symbol} offset={offset}",
        )
        page = result.data or []
        if not page:
            break
        for row in page:
            stamp = pd.to_datetime(row.get("time"), errors="coerce", utc=True)
            if pd.isna(stamp):
                raise ValueError(f"Invalid intraday warm-up timestamp symbol={symbol}")
            local_date = stamp.tz_convert(VN_TZ).date()
            if local_date not in observed:
                if len(observed) == trading_sessions:
                    break
                observed.append(local_date)
            rows.append(row)
        if len(page) < page_size:
            break
        offset += page_size
    return list(reversed(rows))


def validate_replace_scope(
    symbols,
    timeframes,
    start,
    end,
) -> tuple[str, str]:
    """Guard destructive rebuild requests before any database operation."""
    normalized_symbols = tuple(symbols or ())
    normalized_timeframes = tuple(timeframes or ())
    if (
        len(normalized_symbols) != 1
        or len(normalized_timeframes) != 1
        or start is None
        or end is None
    ):
        raise ValueError(
            "replace/rebuild-clean requires exactly one symbol, one timeframe, "
            "--from, and --to"
        )
    return str(normalized_symbols[0]).upper(), str(normalized_timeframes[0])


def atomic_replace_features(*, symbols, timeframes, start, end) -> None:
    """Fail safely until an atomic transaction/RPC contract is available."""
    validate_replace_scope(symbols, timeframes, start, end)
    raise RuntimeError(
        "Atomic feature replace is not configured; no feature rows were deleted "
        "or written. Use full mode for non-destructive scoped recomputation."
    )


def log_feature_run(
    symbol: str,
    timeframe: str,
    mode: str,
    raw_rows: int,
    computed_rows: int,
    upserted_rows: int,
    df: pd.DataFrame | None,
) -> None:
    min_time = None
    max_time = None
    if df is not None and not df.empty and "time" in df.columns:
        min_time = pd.to_datetime(df["time"], errors="coerce", utc=True).min()
        max_time = pd.to_datetime(df["time"], errors="coerce", utc=True).max()
    logger.info(
        "Feature calc symbol=%s timeframe=%s mode=%s fetched_raw_rows=%s "
        "computed_rows=%s upserted_rows=%s min_time=%s max_time=%s",
        symbol,
        timeframe,
        mode,
        raw_rows,
        computed_rows,
        upserted_rows,
        min_time,
        max_time,
    )


def normalize_timeframes(timeframes=None) -> tuple[str, ...]:
    if timeframes is None:
        return DEFAULT_FEATURE_TIMEFRAMES
    if isinstance(timeframes, str):
        timeframes = [timeframes]
    normalized = tuple(dict.fromkeys(timeframes))
    unsupported = sorted(set(normalized) - SUPPORTED_TIMEFRAMES)
    if unsupported:
        raise ValueError(
            f"Unsupported timeframe(s): {unsupported}. "
            f"Supported: {sorted(SUPPORTED_TIMEFRAMES)}"
        )
    return normalized


def filter_output_by_time(
    output_df: pd.DataFrame,
    filter_start_utc: pd.Timestamp | None,
    filter_end_utc: pd.Timestamp | None,
) -> pd.DataFrame:
    if output_df.empty:
        return output_df
    computed_time = pd.to_datetime(output_df["time"], utc=True, errors="coerce")
    if filter_start_utc is not None:
        output_df = output_df.loc[computed_time >= filter_start_utc].copy()
        computed_time = computed_time.loc[output_df.index]
    if filter_end_utc is not None:
        output_df = output_df.loc[computed_time < filter_end_utc].copy()
    return output_df


def upsert_feature_frame(
    db: SupabaseClient,
    symbol: str,
    timeframe: str,
    output_df: pd.DataFrame,
    upsert_batch_size: int,
) -> int:
    records = build_feature_records(output_df, symbol, timeframe)
    if records:
        db._upsert_in_batches(
            "features",
            records,
            on_conflict="symbol,timeframe,time",
            batch_size=upsert_batch_size,
        )
    return len(records)


def run_source_summary(
    flow: str,
    symbols,
    mode: str,
    target_date,
    timeframes: tuple[str, ...],
    per_symbol,
    as_of=None,
) -> dict:
    db = SupabaseClient()
    if not db.health_check():
        raise RuntimeError(
            "Supabase health-check failed. Please check connection and credentials."
        )
    if symbols is None:
        result = db.get().table("symbols").select("symbol").execute()
        symbols = [row["symbol"] for row in result.data]
    symbols = [str(symbol).upper() for symbol in symbols]
    if mode not in {"full", "incremental"}:
        raise ValueError("mode must be either 'full' or 'incremental'")

    target = normalize_target_date(target_date) if mode == "incremental" else None
    records = {timeframe: 0 for timeframe in timeframes}
    errors: list[dict] = []
    total = 0
    successes = 0

    for symbol in symbols:
        try:
            kwargs = {
                "symbol": symbol,
                "mode": mode,
                "target_date": target,
                "records_by_timeframe": records,
            }
            if flow == "features-intraday":
                kwargs.update(timeframes=timeframes, as_of=as_of)
            total += per_symbol(**kwargs)
            successes += 1
        except Exception as exc:
            logger.exception("%s failed symbol=%s mode=%s", flow, symbol, mode)
            errors.append({"symbol": symbol, "error": str(exc)})

    failed = len(errors)
    status = (
        "FAILED"
        if failed == len(symbols) or total == 0
        else ("PARTIAL" if failed else "OK")
    )
    return {
        "flow": flow,
        "mode": mode,
        "target_date": target.isoformat() if target else None,
        "requested_symbols": len(symbols),
        "successful_symbols": successes,
        "failed_symbols": failed,
        "total_records": total,
        "records_by_timeframe": records,
        "errors": errors,
        "status": status,
    }
