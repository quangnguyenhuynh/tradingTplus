import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np

import pandas as pd

from src.database.client import SupabaseClient
from src.utils.time_utils import app_now_iso
from src.engine.feature_calculator import (
    INTRADAY_TIMEFRAMES,
    SUPPORTED_TIMEFRAMES,
    aggregate_timeframe,
    compute_daily_features,
    compute_intraday_features,
    compute_feature_dataframe,
)

logger = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UTC_TZ = ZoneInfo("UTC")
SOURCE_TIMEFRAME = '1m'
DEFAULT_FEATURE_TIMEFRAMES = ('1m', '5m', '15m', '60m', '1d')



def _normalize_target_date(target_date=None) -> date:
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
    raise ValueError(f"target_date must be date, YYYY-MM-DD, or DD/MM/YYYY; got {target_date!r}")


def _target_utc_bounds(target_date=None) -> tuple[pd.Timestamp, pd.Timestamp, date]:
    target = _normalize_target_date(target_date)
    start_vn = datetime.combine(target, datetime.min.time(), tzinfo=VN_TZ)
    end_vn = start_vn + pd.Timedelta(days=1)
    return pd.Timestamp(start_vn.astimezone(UTC_TZ)), pd.Timestamp(end_vn.astimezone(UTC_TZ)), target

FEATURE_COLUMNS = [
    'open', 'high', 'low', 'close', 'volume', 'value',
    'return_1m', 'return_5m', 'return_15m', 'return_from_open', 'return_from_prev_close',
    'ema9', 'ema20', 'ema50', 'ema9_above_ema20', 'ema20_above_ema50',
    'rsi14', 'macd', 'macd_signal', 'macd_histogram',
    'volume_ma20', 'volume_ratio', 'value_ma20', 'value_ratio',
    'high_20_bars', 'low_20_bars', 'close_above_high_20', 'close_below_low_20',
    'vwap_intraday', 'close_above_vwap', 'distance_to_vwap_pct',
    'candle_range', 'candle_body', 'candle_body_pct', 'close_position_in_candle',
]


def _build_feature_records(df: pd.DataFrame, symbol: str, timeframe: str) -> list[dict]:
    if df.empty:
        return []

    last_updated_at = app_now_iso()
    out = df[['time'] + FEATURE_COLUMNS].copy()
    out.insert(0, 'symbol', symbol)
    out.insert(1, 'timeframe', timeframe)
    out['time'] = pd.to_datetime(out['time'], utc=True, errors='coerce')

    numeric_cols = [
        'open', 'high', 'low', 'close', 'volume', 'value',
        'return_1m', 'return_5m', 'return_15m', 'return_from_open', 'return_from_prev_close',
        'ema9', 'ema20', 'ema50', 'rsi14', 'macd', 'macd_signal', 'macd_histogram',
        'volume_ma20', 'volume_ratio', 'value_ma20', 'value_ratio',
        'high_20_bars', 'low_20_bars', 'vwap_intraday', 'distance_to_vwap_pct',
        'candle_range', 'candle_body', 'candle_body_pct', 'close_position_in_candle',
    ]
    out[numeric_cols] = out[numeric_cols].round(6)
    out[numeric_cols] = out[numeric_cols].replace([float('inf'), float('-inf')], pd.NA)
    out['last_updated_at'] = last_updated_at
    out = out.where(pd.notna(out), None)

    records: list[dict] = []
    for row in out.to_dict('records'):
        clean_row = {}
        for key, value in row.items():
            if value is pd.NA or value is pd.NaT:
                clean_row[key] = None
            elif isinstance(value, (float, np.floating)):
                fv = float(value)
                clean_row[key] = None if np.isnan(fv) or np.isinf(fv) else fv
            elif isinstance(value, (int, np.integer)):
                clean_row[key] = int(value)
            elif isinstance(value, pd.Timestamp):
                if pd.isna(value):
                    clean_row[key] = None
                else:
                    clean_row[key] = value.tz_convert('UTC').strftime('%Y-%m-%dT%H:%M:%SZ')
            elif isinstance(value, datetime):
                ts = pd.Timestamp(value)
                if ts.tzinfo is None:
                    ts = ts.tz_localize('UTC')
                clean_row[key] = ts.tz_convert('UTC').strftime('%Y-%m-%dT%H:%M:%SZ')
            else:
                clean_row[key] = value
        records.append(clean_row)
    return records


def _fetch_stock_daily_rows(
    db: SupabaseClient,
    symbol: str,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    order_desc: bool = False,
    limit_total: int | None = None,
) -> list[dict]:
    query = (
        db.get().table('stock_daily')
        .select('trading_date, open_price, highest_price, lowest_price, close_price, total_traded_vol, total_traded_value, total_match_vol, total_match_val')
        .eq('symbol', symbol)
        .order('trading_date', desc=order_desc)
    )
    if start_date is not None:
        query = query.gte('trading_date', str(start_date))
    if end_date is not None:
        query = query.lte('trading_date', str(end_date))
    if limit_total is not None:
        query = query.range(0, limit_total - 1)
    result = db._with_retry(
        lambda q=query: q.execute(),
        action_name=f"fetch stock_daily {symbol}",
    )
    rows = result.data or []
    if order_desc:
        rows = list(reversed(rows))
    return rows


def _date_bounds_for_daily_context(rows: list[dict]) -> tuple[date, date] | None:
    if not rows:
        return None
    times = pd.to_datetime([row.get('time') for row in rows], errors='coerce', utc=True)
    times = pd.Series(times).dropna()
    if times.empty:
        return None
    local_dates = times.dt.tz_convert(VN_TZ).dt.date
    return local_dates.min() - pd.Timedelta(days=14), local_dates.max()


def _fetch_stock_intraday_paginated(
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
            db.get().table('stock_intraday')
            .select('time, open, high, low, close, volume, value')
            .eq('symbol', symbol)
            .eq('timeframe', SOURCE_TIMEFRAME)
        )
        if gte_time is not None:
            query = query.gte('time', gte_time)
        if lt_time is not None:
            query = query.lt('time', lt_time)
        query = query.order('time', desc=order_desc).range(offset, offset + page_size - 1)
        result = db._with_retry(
            lambda q=query: q.execute(),
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


def _log_feature_run(symbol: str, timeframe: str, mode: str, raw_rows: int, computed_rows: int, upserted_rows: int, df: pd.DataFrame | None) -> None:
    min_time = None
    max_time = None
    if df is not None and not df.empty and 'time' in df.columns:
        min_time = pd.to_datetime(df['time'], errors='coerce', utc=True).min()
        max_time = pd.to_datetime(df['time'], errors='coerce', utc=True).max()
    logger.info(
        "Feature calc symbol=%s timeframe=%s mode=%s fetched_raw_rows=%s computed_rows=%s upserted_rows=%s min_time=%s max_time=%s",
        symbol, timeframe, mode, raw_rows, computed_rows, upserted_rows, min_time, max_time
    )


def _normalize_timeframes(timeframes=None) -> tuple[str, ...]:
    if timeframes is None:
        return DEFAULT_FEATURE_TIMEFRAMES
    if isinstance(timeframes, str):
        timeframes = [timeframes]
    normalized = tuple(dict.fromkeys(timeframes))
    unsupported = sorted(set(normalized) - SUPPORTED_TIMEFRAMES)
    if unsupported:
        raise ValueError(f"Unsupported timeframe(s): {unsupported}. Supported: {sorted(SUPPORTED_TIMEFRAMES)}")
    return normalized


def _filter_output_by_time(output_df: pd.DataFrame, filter_start_utc: pd.Timestamp | None, filter_end_utc: pd.Timestamp | None) -> pd.DataFrame:
    if output_df.empty:
        return output_df
    if filter_start_utc is not None:
        computed_time = pd.to_datetime(output_df['time'], utc=True, errors='coerce')
        output_df = output_df.loc[computed_time >= filter_start_utc].copy()
    if filter_end_utc is not None:
        computed_time = pd.to_datetime(output_df['time'], utc=True, errors='coerce')
        output_df = output_df.loc[computed_time < filter_end_utc].copy()
    return output_df


def _upsert_feature_frame(db: SupabaseClient, symbol: str, timeframe: str, output_df: pd.DataFrame, upsert_batch_size: int) -> int:
    records = _build_feature_records(output_df, symbol, timeframe)
    if records:
        db._upsert_in_batches('features', records, on_conflict='symbol,timeframe,time', batch_size=upsert_batch_size)
    return len(records)


def _compute_and_upsert_timeframes(
    db: SupabaseClient,
    symbol: str,
    source_rows: list[dict],
    timeframes=None,
    mode: str = 'full',
    upsert_batch_size: int = 1000,
    filter_start_utc: pd.Timestamp | None = None,
    filter_end_utc: pd.Timestamp | None = None,
    daily_rows: list[dict] | None = None,
    records_by_timeframe: dict[str, int] | None = None,
) -> int:
    normalized_timeframes = _normalize_timeframes(timeframes)
    source_df = pd.DataFrame(source_rows or [])
    daily_df = pd.DataFrame(daily_rows or [])
    total_upserted = 0

    for timeframe in normalized_timeframes:
        if timeframe == '1d':
            if daily_df.empty:
                _log_feature_run(symbol, timeframe, mode, 0, 0, 0, None)
                continue
            computed_df = compute_daily_features(daily_df)
            output_df = _filter_output_by_time(computed_df, filter_start_utc, filter_end_utc)
            upserted = _upsert_feature_frame(db, symbol, timeframe, output_df, upsert_batch_size)
            total_upserted += upserted
            if records_by_timeframe is not None:
                records_by_timeframe[timeframe] = records_by_timeframe.get(timeframe, 0) + upserted
            _log_feature_run(symbol, timeframe, mode, len(daily_df), len(computed_df), upserted, output_df)
            continue

        if source_df.empty:
            _log_feature_run(symbol, timeframe, mode, 0, 0, 0, None)
            continue
        aggregated_df = aggregate_timeframe(source_df, timeframe)
        if aggregated_df.empty:
            _log_feature_run(symbol, timeframe, mode, len(source_df), 0, 0, aggregated_df)
            continue

        computed_df = compute_intraday_features(aggregated_df, timeframe=timeframe, daily_df=daily_df)
        output_df = _filter_output_by_time(computed_df, filter_start_utc, filter_end_utc)
        upserted = _upsert_feature_frame(db, symbol, timeframe, output_df, upsert_batch_size)
        total_upserted += upserted
        if records_by_timeframe is not None:
            records_by_timeframe[timeframe] = records_by_timeframe.get(timeframe, 0) + upserted
        _log_feature_run(symbol, timeframe, mode, len(source_df), len(computed_df), upserted, output_df)

    return total_upserted

def calculate_features_for_symbol_full_chunked(symbol, timeframes=None, upsert_batch_size=1000):
    db = SupabaseClient()
    rows = _fetch_stock_intraday_paginated(db=db, symbol=symbol, order_desc=False)
    bounds = _date_bounds_for_daily_context(rows)
    daily_rows = _fetch_stock_daily_rows(db, symbol, bounds[0], bounds[1]) if bounds else []
    if '1d' in _normalize_timeframes(timeframes) and not daily_rows:
        daily_rows = _fetch_stock_daily_rows(db, symbol)
    return _compute_and_upsert_timeframes(
        db=db,
        symbol=symbol,
        source_rows=rows,
        timeframes=timeframes,
        mode='full',
        upsert_batch_size=upsert_batch_size,
        daily_rows=daily_rows,
    )


def calculate_features_for_symbol_incremental(symbol, timeframes=None, target_date=None, warmup_bars: int = 300, upsert_batch_size: int = 1000, records_by_timeframe: dict[str, int] | None = None):
    db = SupabaseClient()
    start_utc, end_utc, target = _target_utc_bounds(target_date)

    today_rows = _fetch_stock_intraday_paginated(
        db=db,
        symbol=symbol,
        gte_time=start_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
        lt_time=end_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
        order_desc=False,
    )
    normalized_timeframes = _normalize_timeframes(timeframes)
    if not today_rows and any(tf in INTRADAY_TIMEFRAMES for tf in normalized_timeframes):
        for timeframe in normalized_timeframes:
            if timeframe in INTRADAY_TIMEFRAMES:
                _log_feature_run(symbol, timeframe, "incremental", 0, 0, 0, None)

    warmup_rows = _fetch_stock_intraday_paginated(
        db=db,
        symbol=symbol,
        lt_time=start_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
        order_desc=True,
        limit_total=warmup_bars,
    )
    warmup_rows = list(reversed(warmup_rows))
    daily_rows = _fetch_stock_daily_rows(db, symbol, end_date=target, order_desc=True, limit_total=150)

    return _compute_and_upsert_timeframes(
        db=db,
        symbol=symbol,
        source_rows=warmup_rows + today_rows,
        timeframes=normalized_timeframes,
        mode='incremental',
        upsert_batch_size=upsert_batch_size,
        filter_start_utc=start_utc,
        filter_end_utc=end_utc,
        daily_rows=daily_rows,
        records_by_timeframe=records_by_timeframe,
    )


def calculate_features_for_symbol(symbol, timeframe='1m'):
    """Backward-compatible wrapper used by older utility modules."""
    return calculate_features_for_symbol_full_chunked(symbol, timeframes=[timeframe])


def run_feature_engine(symbols=None, mode='full', timeframes=None, target_date=None):
    db = SupabaseClient()

    if not db.health_check():
        raise RuntimeError("Supabase health-check failed. Please check connection and credentials.")

    if symbols is None:
        result = db.get().table('symbols').select('symbol').execute()
        symbols = [row['symbol'] for row in result.data]

    if mode not in {'full', 'incremental'}:
        raise ValueError("mode must be either 'full' or 'incremental'")

    timeframes = _normalize_timeframes(timeframes)
    logger.info("Start feature engine for %s symbols mode=%s timeframes=%s", len(symbols), mode, timeframes)

    total = 0
    for symbol in symbols:
        try:
            if mode == 'full':
                total += calculate_features_for_symbol_full_chunked(symbol, timeframes=timeframes)
            else:
                total += calculate_features_for_symbol_incremental(symbol, timeframes=timeframes, target_date=target_date)
        except Exception:
            logger.exception("Feature engine failed for symbol=%s mode=%s", symbol, mode)

    logger.info("Feature engine completed with %s records", total)
    return total


def run_feature_engine_with_summary(symbols=None, mode='full', timeframes=None, target_date=None):
    db = SupabaseClient()
    if not db.health_check():
        raise RuntimeError("Supabase health-check failed. Please check connection and credentials.")
    if symbols is None:
        result = db.get().table('symbols').select('symbol').execute()
        symbols = [row['symbol'] for row in result.data]
    symbols = [str(s).upper() for s in symbols]
    if mode not in {'full', 'incremental'}:
        raise ValueError("mode must be either 'full' or 'incremental'")
    normalized_timeframes = _normalize_timeframes(timeframes)
    target = _normalize_target_date(target_date) if mode == 'incremental' else None
    errors = []
    records_by_timeframe = {tf: 0 for tf in normalized_timeframes}
    total = 0
    success = 0
    for symbol in symbols:
        try:
            if mode == 'full':
                count = calculate_features_for_symbol_full_chunked(symbol, timeframes=normalized_timeframes)
            else:
                count = calculate_features_for_symbol_incremental(symbol, timeframes=normalized_timeframes, target_date=target, records_by_timeframe=records_by_timeframe)
            total += count
            success += 1
        except Exception as exc:
            logger.exception("Feature engine failed for symbol=%s mode=%s", symbol, mode)
            errors.append({"symbol": symbol, "error": str(exc)})
    failed = len(errors)
    if failed == len(symbols) or total == 0:
        status = "FAILED"
    elif failed:
        status = "PARTIAL"
    else:
        status = "OK"
    return {
        "flow": "features",
        "mode": mode,
        "target_date": target.isoformat() if target else None,
        "requested_symbols": len(symbols),
        "successful_symbols": success,
        "failed_symbols": failed,
        "total_records": total,
        "records_by_timeframe": records_by_timeframe,
        "errors": errors,
        "status": status,
    }


if __name__ == "__main__":
    import argparse
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
    parser = argparse.ArgumentParser(description="Run feature engine")
    parser.add_argument("--mode", choices=["full", "incremental"], default="full")
    parser.add_argument("--timeframes", nargs="*", default=list(DEFAULT_FEATURE_TIMEFRAMES))
    parser.add_argument("--symbols", nargs="*", default=['SSI', 'SHB', 'HPG', 'FPT'])
    args = parser.parse_args()
    logger.info("Symbols: %s mode=%s timeframes=%s", args.symbols, args.mode, args.timeframes)
    run_feature_engine(args.symbols, mode=args.mode, timeframes=args.timeframes)
