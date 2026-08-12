"""Shared database/runtime plumbing for source-specific feature flows."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
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
BIGINT_ROUNDING_ARTIFACT_TOLERANCE = 0.05
PERSISTED_REPLACE_TIMEFRAMES = frozenset({"1d", "15m", "60m"})


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
        if np.isfinite(numeric):
            rounded = round(numeric)
            if abs(numeric - rounded) < BIGINT_ROUNDING_ARTIFACT_TOLERANCE:
                return int(rounded)
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
    page_size: int = 1000,
) -> list[dict]:
    """Read all matching daily rows without relying on PostgREST's row cap.

    Descending reads are used to obtain the newest N source rows, but this
    function preserves the calculator contract by returning those rows oldest
    first.
    """
    if page_size <= 0:
        raise ValueError("page_size must be greater than zero")
    if limit_total is not None and limit_total < 0:
        raise ValueError("limit_total must be non-negative")
    if limit_total == 0:
        return []

    offset = 0
    page_number = 0
    rows_all: list[dict] = []
    previous_page: tuple | None = None
    while limit_total is None or len(rows_all) < limit_total:
        requested = page_size
        if limit_total is not None:
            requested = min(requested, limit_total - len(rows_all))
        query = (
            db.get().table("stock_daily")
            .select(
                "trading_date, open_price, highest_price, lowest_price, close_price, "
                "total_traded_vol, total_traded_value, total_match_vol, total_match_val"
            )
            .eq("symbol", symbol)
        )
        if start_date is not None:
            query = query.gte("trading_date", str(start_date))
        if end_date is not None:
            query = query.lte("trading_date", str(end_date))
        query = query.order("trading_date", desc=order_desc).range(
            offset, offset + requested - 1
        )
        page_number += 1
        result = db._with_retry(
            lambda current_query=query: current_query.execute(),
            action_name=(
                f"fetch stock_daily symbol={symbol} page={page_number} "
                f"offset={offset}"
            ),
        )
        page = result.data or []
        if not page:
            break
        page_identity = tuple(row.get("trading_date") for row in page)
        if page_identity == previous_page:
            raise RuntimeError(
                f"Repeated PostgREST page table=stock_daily symbol={symbol} "
                f"page={page_number} offset={offset} returned={len(page)}"
            )
        previous_page = page_identity
        rows_all.extend(page)
        logger.info(
            "stock_daily page symbol=%s page=%s offset=%s requested=%s rows=%s",
            symbol, page_number, offset, requested, len(page),
        )
        offset += len(page)

    logger.info(
        "stock_daily fetch complete symbol=%s pages=%s rows=%s start=%s end=%s desc=%s limit=%s",
        symbol, page_number, len(rows_all), start_date, end_date, order_desc, limit_total,
    )
    return list(reversed(rows_all)) if order_desc else rows_all


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
    if page_size <= 0:
        raise ValueError("page_size must be greater than zero")
    if limit_total is not None and limit_total < 0:
        raise ValueError("limit_total must be non-negative")
    if limit_total == 0:
        return []
    offset = 0
    rows_all: list[dict] = []
    page_number = 0
    previous_page: tuple | None = None

    while limit_total is None or len(rows_all) < limit_total:
        requested = page_size
        if limit_total is not None:
            requested = min(requested, limit_total - len(rows_all))
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
            offset + requested - 1,
        )
        page_number += 1
        result = db._with_retry(
            lambda current_query=query: current_query.execute(),
            action_name=(f"fetch stock_intraday table=stock_intraday symbol={symbol} "
                         f"page={page_number} offset={offset}"),
        )
        page_rows = result.data or []
        if not page_rows:
            break
        page_identity = tuple(row.get("time") for row in page_rows)
        if page_identity == previous_page:
            raise RuntimeError(
                f"Repeated PostgREST page table=stock_intraday symbol={symbol} "
                f"page={page_number} offset={offset} returned={len(page_rows)}"
            )
        previous_page = page_identity

        rows_all.extend(page_rows)
        if limit_total is not None and len(rows_all) >= limit_total:
            return rows_all[:limit_total]
        offset += len(page_rows)

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
    if page_size <= 0:
        raise ValueError("page_size must be greater than zero")
    offset = 0
    rows: list[dict] = []
    observed: list[date] = []
    oldest_selected: date | None = None
    previous_page: tuple | None = None
    page_number = 0
    done = False
    while not done:
        query = (
            db.get().table("stock_intraday")
            .select("time, open, high, low, close, volume, value")
            .eq("symbol", symbol).eq("timeframe", SOURCE_TIMEFRAME)
            .lt("time", lt_time).order("time", desc=True)
            .range(offset, offset + page_size - 1)
        )
        result = db._with_retry(
            lambda current_query=query: current_query.execute(),
            action_name=(f"fetch intraday warm-up table=stock_intraday symbol={symbol} "
                         f"page={page_number + 1} offset={offset}"),
        )
        page_number += 1
        page = result.data or []
        if not page:
            break
        page_identity = tuple(row.get("time") for row in page)
        if page_identity == previous_page:
            raise RuntimeError(
                f"Repeated PostgREST page table=stock_intraday symbol={symbol} "
                f"page={page_number} offset={offset} returned={len(page)}"
            )
        previous_page = page_identity
        for row in page:
            stamp = pd.to_datetime(row.get("time"), errors="coerce", utc=True)
            if pd.isna(stamp):
                raise ValueError(f"Invalid intraday warm-up timestamp symbol={symbol}")
            local_date = stamp.tz_convert(VN_TZ).date()
            if local_date not in observed:
                if oldest_selected is not None and local_date < oldest_selected:
                    done = True
                    break
                observed.append(local_date)
                if len(observed) == trading_sessions:
                    oldest_selected = local_date
            rows.append(row)
        offset += len(page)
    return list(reversed(rows))


def validate_replace_scope(
    symbols,
    timeframes,
    start,
    end,
) -> tuple[str, str]:
    """Guard destructive rebuild requests before any database operation."""
    normalized_symbols = tuple(
        str(symbol).strip().upper() for symbol in (symbols or ())
    )
    normalized_timeframes = tuple(
        str(timeframe).strip() for timeframe in (timeframes or ())
    )
    if (
        len(normalized_symbols) != 1
        or len(normalized_timeframes) != 1
        or not normalized_symbols[0]
        or not normalized_timeframes[0]
        or start is None
        or end is None
    ):
        raise ValueError(
            "replace/rebuild-clean requires exactly one symbol, one timeframe, "
            "--from, and --to"
        )
    timeframe = normalized_timeframes[0]
    if normalized_symbols[0] in {"*", "%", "ALL"} or any(
        marker in normalized_symbols[0] for marker in ("*", "%", ",")
    ):
        raise ValueError("replace/rebuild-clean requires one exact symbol without wildcards")
    if timeframe not in PERSISTED_REPLACE_TIMEFRAMES:
        raise ValueError(
            "replace/rebuild-clean supports only persisted feature timeframes "
            "1d, 15m, and 60m"
        )

    def parse_bound(value, name: str) -> pd.Timestamp:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                raise ValueError(f"replace/rebuild-clean {name} cannot be empty")
            try:
                parsed_date = normalize_target_date(text)
            except ValueError:
                try:
                    stamp = pd.Timestamp(text)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"replace/rebuild-clean {name} is not a valid date/time"
                    ) from exc
            else:
                stamp = pd.Timestamp(parsed_date, tz=VN_TZ)
        elif isinstance(value, date) and not isinstance(value, datetime):
            stamp = pd.Timestamp(value, tz=VN_TZ)
        else:
            try:
                stamp = pd.Timestamp(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"replace/rebuild-clean {name} is not a valid date/time"
                ) from exc
        if pd.isna(stamp):
            raise ValueError(f"replace/rebuild-clean {name} is not a valid date/time")
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize(VN_TZ)
        return stamp.tz_convert(UTC_TZ)

    start_stamp = parse_bound(start, "start")
    end_stamp = parse_bound(end, "end")
    if start_stamp > end_stamp:
        raise ValueError("replace/rebuild-clean start must be <= end")
    return normalized_symbols[0], timeframe


def replace_utc_bounds(start, end) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Convert inclusive Vietnam CLI dates to a half-open UTC interval."""
    start_date = normalize_target_date(start)
    end_date = normalize_target_date(end)
    if start_date > end_date:
        raise ValueError("replace/rebuild-clean start must be <= end")
    return target_utc_bounds(start_date)[0], target_utc_bounds(end_date + timedelta(days=1))[0]


def _validate_replacement_records(records, symbol, timeframe, start_utc, end_exclusive_utc):
    if not records:
        raise ValueError("replacement dataset is empty; refusing atomic replace")
    required = {"symbol", "timeframe", "time", *FEATURE_COLUMNS}
    keys: set[tuple[str, str, pd.Timestamp]] = set()
    stamps = []
    for index, row in enumerate(records):
        missing = required - set(row)
        if missing:
            raise ValueError(f"replacement row {index} is missing columns: {sorted(missing)}")
        if row["symbol"] != symbol or row["timeframe"] != timeframe:
            raise ValueError(f"replacement row {index} is outside symbol/timeframe scope")
        stamp = pd.to_datetime(row["time"], errors="coerce", utc=True)
        if pd.isna(stamp) or not start_utc <= stamp < end_exclusive_utc:
            raise ValueError(f"replacement row {index} has invalid or out-of-scope time")
        key = (symbol, timeframe, stamp)
        if key in keys:
            raise ValueError("replacement dataset contains duplicate symbol/timeframe/time")
        keys.add(key)
        stamps.append(stamp)
    return min(stamps), max(stamps)


def atomic_replace_features(*, symbols, timeframes, start, end) -> dict:
    """Compute a complete scoped dataset, then replace it with one atomic RPC."""
    symbol, timeframe = validate_replace_scope(symbols, timeframes, start, end)
    start_utc, end_exclusive_utc = replace_utc_bounds(start, end)
    db = SupabaseClient()
    if not db.health_check():
        raise RuntimeError("Supabase health-check failed before atomic replace")

    if timeframe == "1d":
        from .daily import compute_daily_features
        warmup_start = (start_utc - pd.DateOffset(years=5)).tz_convert(VN_TZ).date()
        source_rows = fetch_stock_daily_rows(
            db, symbol, start_date=warmup_start,
            end_date=(end_exclusive_utc - pd.Timedelta(days=1)).tz_convert(VN_TZ).date(),
        )
        computed = compute_daily_features(pd.DataFrame(source_rows)) if source_rows else pd.DataFrame()
        source_table = "stock_daily"
    else:
        from .intraday import aggregate_timeframe, compute_intraday_features, filter_closed_buckets, _resolve_as_of
        warmup_rows = fetch_intraday_trading_session_window(
            db, symbol, start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), trading_sessions=250
        )
        target_rows = fetch_stock_intraday_paginated(
            db, symbol,
            gte_time=start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            lt_time=end_exclusive_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        source_rows = warmup_rows + target_rows
        bounds = date_bounds_for_daily_context(source_rows)
        daily_rows = fetch_stock_daily_rows(db, symbol, bounds[0], bounds[1]) if bounds else []
        aggregated = aggregate_timeframe(pd.DataFrame(source_rows), timeframe) if source_rows else pd.DataFrame()
        closed = filter_closed_buckets(
            aggregated, timeframe,
            _resolve_as_of((end_exclusive_utc - pd.Timedelta(days=1)).tz_convert(VN_TZ).date(), None),
        ) if not aggregated.empty else aggregated
        computed = compute_intraday_features(closed, timeframe, pd.DataFrame(daily_rows)) if not closed.empty else closed
        source_table = "stock_intraday"

    output = filter_output_by_time(computed, start_utc, end_exclusive_utc)
    records = build_feature_records(output, symbol, timeframe)
    min_time, max_time = _validate_replacement_records(
        records, symbol, timeframe, start_utc, end_exclusive_utc
    )
    logger.info(
        "Atomic replace validated symbol=%s timeframe=%s source=%s source_rows=%s computed=%s selected=%s min=%s max=%s",
        symbol, timeframe, source_table, len(source_rows), len(computed), len(records), min_time, max_time,
    )
    result = db.atomic_replace_features(
        symbol=symbol, timeframe=timeframe,
        start_utc=start_utc.isoformat(), end_exclusive_utc=end_exclusive_utc.isoformat(),
        replacement_rows=records,
    )
    return {
        "flow": "features-replace", "mode": "replace", "status": "OK",
        "symbol": symbol, "timeframe": timeframe, "source_table": source_table,
        "start_utc": start_utc.isoformat(), "end_exclusive_utc": end_exclusive_utc.isoformat(),
        "source_rows": len(source_rows), "computed_rows": len(computed),
        "selected_rows": len(records), "output_min_time": str(min_time),
        "output_max_time": str(max_time), **result,
    }


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
    status = "FAILED" if symbols and failed == len(symbols) else ("PARTIAL" if failed else "OK")
    return {
        "flow": flow,
        "mode": mode,
        "target_date": target.isoformat() if target else None,
        "requested_symbols": len(symbols),
        "successful_symbols": successes,
        "failed_symbols": failed,
        "total_records": total,
        "no_op": total == 0 and failed == 0,
        "no_op_reason": "no source rows selected for write" if total == 0 and failed == 0 else None,
        "records_by_timeframe": records,
        "errors": errors,
        "status": status,
    }
