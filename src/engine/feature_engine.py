import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np

import pandas as pd

from src.database.client import SupabaseClient
from src.engine.feature_calculator import SUPPORTED_TIMEFRAMES, aggregate_timeframe, compute_feature_dataframe

logger = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UTC_TZ = ZoneInfo("UTC")
SOURCE_TIMEFRAME = '1m'
DEFAULT_FEATURE_TIMEFRAMES = ('1m', '5m', '15m', '60m', '1d')

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

    last_updated_at = datetime.now(timezone.utc).isoformat()
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
) -> list[dict]:
    query = (
        db.get().table('stock_daily')
        .select('trading_date, close_price')
        .eq('symbol', symbol)
        .order('trading_date', desc=False)
    )
    if start_date is not None:
        query = query.gte('trading_date', str(start_date))
    if end_date is not None:
        query = query.lte('trading_date', str(end_date))
    result = db._with_retry(
        lambda q=query: q.execute(),
        action_name=f"fetch stock_daily {symbol}",
    )
    return result.data or []


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
) -> int:
    if not source_rows:
        for timeframe in _normalize_timeframes(timeframes):
            _log_feature_run(symbol, timeframe, mode, 0, 0, 0, None)
        return 0

    source_df = pd.DataFrame(source_rows)
    total_upserted = 0
    for timeframe in _normalize_timeframes(timeframes):
        aggregated_df = aggregate_timeframe(source_df, timeframe)
        if aggregated_df.empty:
            _log_feature_run(symbol, timeframe, mode, len(source_df), 0, 0, aggregated_df)
            continue

        computed_df = compute_feature_dataframe(aggregated_df, daily_df=pd.DataFrame(daily_rows or []))
        output_df = computed_df
        if filter_start_utc is not None:
            computed_time = pd.to_datetime(output_df['time'], utc=True, errors='coerce')
            output_df = output_df.loc[computed_time >= filter_start_utc].copy()
        if filter_end_utc is not None:
            computed_time = pd.to_datetime(output_df['time'], utc=True, errors='coerce')
            output_df = output_df.loc[computed_time < filter_end_utc].copy()

        records = _build_feature_records(output_df, symbol, timeframe)
        if records:
            db._upsert_in_batches('features', records, on_conflict='symbol,timeframe,time', batch_size=upsert_batch_size)
        total_upserted += len(records)
        _log_feature_run(symbol, timeframe, mode, len(source_df), len(computed_df), len(records), output_df)

    return total_upserted


def calculate_features_for_symbol_full_chunked(symbol, timeframes=None, upsert_batch_size=1000):
    db = SupabaseClient()
    rows = _fetch_stock_intraday_paginated(db=db, symbol=symbol, order_desc=False)
    bounds = _date_bounds_for_daily_context(rows)
    daily_rows = _fetch_stock_daily_rows(db, symbol, bounds[0], bounds[1]) if bounds else []
    return _compute_and_upsert_timeframes(
        db=db,
        symbol=symbol,
        source_rows=rows,
        timeframes=timeframes,
        mode='full',
        upsert_batch_size=upsert_batch_size,
        daily_rows=daily_rows,
    )


def calculate_features_for_symbol_incremental(symbol, timeframes=None, warmup_bars: int = 300, upsert_batch_size: int = 1000):
    db = SupabaseClient()
    now_vn = datetime.now(VN_TZ)
    today_start_vn = now_vn.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start_vn = today_start_vn + pd.Timedelta(days=1)
    today_start_utc = today_start_vn.astimezone(UTC_TZ)
    tomorrow_start_utc = tomorrow_start_vn.astimezone(UTC_TZ)

    today_rows = _fetch_stock_intraday_paginated(
        db=db,
        symbol=symbol,
        gte_time=today_start_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
        lt_time=tomorrow_start_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
        order_desc=False,
    )
    if not today_rows:
        for timeframe in _normalize_timeframes(timeframes):
            _log_feature_run(symbol, timeframe, "incremental", 0, 0, 0, None)
        return 0

    warmup_rows = _fetch_stock_intraday_paginated(
        db=db,
        symbol=symbol,
        lt_time=today_start_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
        order_desc=True,
        limit_total=warmup_bars,
    )
    warmup_rows = list(reversed(warmup_rows))
    daily_start_vn = (today_start_vn.date() - pd.Timedelta(days=14))
    daily_rows = _fetch_stock_daily_rows(db, symbol, daily_start_vn, today_start_vn.date())

    return _compute_and_upsert_timeframes(
        db=db,
        symbol=symbol,
        source_rows=warmup_rows + today_rows,
        timeframes=timeframes,
        mode='incremental',
        upsert_batch_size=upsert_batch_size,
        filter_start_utc=pd.Timestamp(today_start_utc),
        filter_end_utc=pd.Timestamp(tomorrow_start_utc),
        daily_rows=daily_rows,
    )


def calculate_features_for_symbol(symbol, timeframe='1m'):
    """Backward-compatible wrapper used by older utility modules."""
    return calculate_features_for_symbol_full_chunked(symbol, timeframes=[timeframe])


def run_feature_engine(symbols=None, mode='full', timeframes=None):
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
                total += calculate_features_for_symbol_incremental(symbol, timeframes=timeframes)
        except Exception:
            logger.exception("Feature engine failed for symbol=%s mode=%s", symbol, mode)

    logger.info("Feature engine completed with %s records", total)
    return total


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
