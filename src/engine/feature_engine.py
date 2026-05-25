import logging
from datetime import datetime

import pandas as pd

from src.database.client import SupabaseClient
from src.engine.feature_calculator import compute_feature_dataframe

logger = logging.getLogger(__name__)

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
    last_updated_at = datetime.now().isoformat()
    out = df[['time'] + FEATURE_COLUMNS].copy()
    out.insert(0, 'symbol', symbol)
    out.insert(1, 'timeframe', timeframe)
    out['time'] = out['time'].dt.strftime('%Y-%m-%dT%H:%M:%S%z')

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
    return out.to_dict('records')


def calculate_features_for_symbol(symbol, timeframe='1m', fetch_batch_size=1000):
    db = SupabaseClient()
    logger.info("Calculating features for symbol=%s timeframe=%s", symbol, timeframe)

    offset = 0
    total_records = 0
    window_df = pd.DataFrame()

    while True:
        result = db._with_retry(
            lambda: db.get().table('stock_intraday')
            .select('time, open, high, low, close, volume, value')
            .eq('symbol', symbol)
            .eq('timeframe', timeframe)
            .order('time', desc=False)
            .range(offset, offset + fetch_batch_size - 1)
            .execute(),
            action_name=f"fetch stock_intraday {symbol} offset={offset}",
        )
        rows = result.data or []
        if not rows:
            break

        batch_df = pd.DataFrame(rows)
        batch_df['time'] = pd.to_datetime(batch_df['time'])

        window_df = pd.concat([window_df, batch_df], ignore_index=True)
        window_df = compute_feature_dataframe(window_df)

        warmup = 80
        upsert_df = window_df.iloc[:-warmup] if len(rows) == fetch_batch_size and len(window_df) > warmup else window_df
        records = _build_feature_records(upsert_df, symbol, timeframe)

        if records:
            db.upsert_features(records)
            total_records += len(records)
            logger.info("Upserted %s features for %s (offset=%s)", len(records), symbol, offset)

        window_df = window_df.iloc[-warmup:].copy() if len(upsert_df) < len(window_df) else pd.DataFrame()
        offset += fetch_batch_size

    logger.info("Done symbol=%s total_feature_records=%s", symbol, total_records)
    return total_records


def run_feature_engine(symbols=None):
    db = SupabaseClient()

    if not db.health_check():
        raise RuntimeError("Supabase health-check failed. Please check connection and credentials.")

    if symbols is None:
        result = db.get().table('symbols').select('symbol').execute()
        symbols = [row['symbol'] for row in result.data]

    logger.info("Start feature engine for %s symbols", len(symbols))

    total = 0
    for symbol in symbols:
        try:
            total += calculate_features_for_symbol(symbol)
        except Exception:
            logger.exception("Feature engine failed for symbol=%s", symbol)

    logger.info("Feature engine completed with %s records", total)
    return total


if __name__ == "__main__":
    import logging
    import sys

    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')

    symbols = sys.argv[1:] if len(sys.argv) > 1 else ['SSI', 'SHB', 'HPG', 'FPT']
    logger.info("Symbols: %s", symbols)
    run_feature_engine(symbols)
