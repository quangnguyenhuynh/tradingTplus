import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np

import pandas as pd

from src.database.client import SupabaseClient
from src.engine.feature_calculator import compute_feature_dataframe

logger = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

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

    last_updated_at = datetime.now().isoformat()
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


def calculate_features_for_symbol_full(symbol, timeframe='1m', upsert_batch_size: int = 1000):
    db = SupabaseClient()
    result = db._with_retry(
        lambda: db.get().table('stock_intraday')
        .select('time, open, high, low, close, volume, value')
        .eq('symbol', symbol)
        .eq('timeframe', timeframe)
        .order('time', desc=False)
        .execute(),
        action_name=f"fetch full stock_intraday {symbol}",
    )
    rows = result.data or []
    if not rows:
        _log_feature_run(symbol, timeframe, "full", 0, 0, 0, None)
        return 0

    raw_df = pd.DataFrame(rows)
    computed_df = compute_feature_dataframe(raw_df)
    records = _build_feature_records(computed_df, symbol, timeframe)
    if records:
        db._upsert_in_batches('features', records, on_conflict='symbol,timeframe,time', batch_size=upsert_batch_size)
    _log_feature_run(symbol, timeframe, "full", len(raw_df), len(computed_df), len(records), computed_df)
    return len(records)


def calculate_features_for_symbol_incremental(symbol, timeframe='1m', warmup_bars: int = 200, upsert_batch_size: int = 1000):
    db = SupabaseClient()
    now_vn = datetime.now(VN_TZ)
    today_start_vn = now_vn.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = today_start_vn.astimezone(ZoneInfo("UTC"))

    today_result = db._with_retry(
        lambda: db.get().table('stock_intraday')
        .select('time, open, high, low, close, volume, value')
        .eq('symbol', symbol)
        .eq('timeframe', timeframe)
        .gte('time', today_start_utc.strftime('%Y-%m-%dT%H:%M:%SZ'))
        .order('time', desc=False)
        .execute(),
        action_name=f"fetch today stock_intraday {symbol}",
    )
    today_rows = today_result.data or []
    if not today_rows:
        _log_feature_run(symbol, timeframe, "incremental", 0, 0, 0, None)
        return 0

    warmup_result = db._with_retry(
        lambda: db.get().table('stock_intraday')
        .select('time, open, high, low, close, volume, value')
        .eq('symbol', symbol)
        .eq('timeframe', timeframe)
        .lt('time', today_start_utc.strftime('%Y-%m-%dT%H:%M:%SZ'))
        .order('time', desc=True)
        .limit(warmup_bars)
        .execute(),
        action_name=f"fetch warmup stock_intraday {symbol}",
    )
    warmup_rows = list(reversed(warmup_result.data or []))

    combined_df = pd.DataFrame(warmup_rows + today_rows)
    computed_df = compute_feature_dataframe(combined_df)
    trading_date_vn = pd.to_datetime(computed_df['time'], utc=True).dt.tz_convert(VN_TZ).dt.date
    today_date_vn = today_start_vn.date()
    today_df = computed_df.loc[trading_date_vn == today_date_vn].copy()

    records = _build_feature_records(today_df, symbol, timeframe)
    if records:
        db._upsert_in_batches('features', records, on_conflict='symbol,timeframe,time', batch_size=upsert_batch_size)
    _log_feature_run(symbol, timeframe, "incremental", len(combined_df), len(computed_df), len(records), today_df)
    return len(records)


def run_feature_engine(symbols=None, mode='full'):
    db = SupabaseClient()

    if not db.health_check():
        raise RuntimeError("Supabase health-check failed. Please check connection and credentials.")

    if symbols is None:
        result = db.get().table('symbols').select('symbol').execute()
        symbols = [row['symbol'] for row in result.data]

    if mode not in {'full', 'incremental'}:
        raise ValueError("mode must be either 'full' or 'incremental'")

    logger.info("Start feature engine for %s symbols mode=%s", len(symbols), mode)

    total = 0
    for symbol in symbols:
        try:
            if mode == 'full':
                total += calculate_features_for_symbol_full(symbol)
            else:
                total += calculate_features_for_symbol_incremental(symbol)
        except Exception:
            logger.exception("Feature engine failed for symbol=%s mode=%s", symbol, mode)

    logger.info("Feature engine completed with %s records", total)
    return total


if __name__ == "__main__":
    import logging
    import sys

    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')

    symbols = sys.argv[1:] if len(sys.argv) > 1 else ['SSI', 'SHB', 'HPG', 'FPT']
    logger.info("Symbols: %s", symbols)
    run_feature_engine(symbols)
