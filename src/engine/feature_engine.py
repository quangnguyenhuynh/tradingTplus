import logging
from datetime import datetime

import pandas as pd

from src.database.client import SupabaseClient

logger = logging.getLogger(__name__)


def calculate_rsi_wilder(prices, period=14):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta.where(delta < 0, 0))
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_macd(prices, fast=12, slow=26, signal=9):
    exp_fast = prices.ewm(span=fast, adjust=False).mean()
    exp_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = exp_fast - exp_slow
    macd_signal = macd_line.ewm(span=signal, adjust=False).mean()
    macd_histogram = macd_line - macd_signal
    return macd_line, macd_signal, macd_histogram


def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_volume_spike(volume, window=20, std_mult=2.0):
    mean = volume.rolling(window=window).mean()
    std = volume.rolling(window=window).std()
    return (volume > (mean + std_mult * std)).fillna(False)


def calculate_ema(prices, period=20):
    return prices.ewm(span=period, adjust=False).mean()


def calculate_vwap(df):
    price_vol = df['close'] * df['volume']
    return price_vol.cumsum() / df['volume'].cumsum()


def calculate_bollinger_bands(prices, period=20, std_dev=2):
    middle = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return middle, upper, lower


def add_feature_lags(df, columns, lags=(1, 2, 5)):
    for col in columns:
        for lag in lags:
            df[f'{col}_lag{lag}'] = df[col].shift(lag)
    return df


def _compute_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values('time').copy()
    df['rsi'] = calculate_rsi_wilder(df['close'])
    df['macd'], df['macd_signal'], df['macd_histogram'] = calculate_macd(df['close'])
    df['atr'] = calculate_atr(df)
    df['volume_spike'] = calculate_volume_spike(df['volume'])
    df['ema_20'] = calculate_ema(df['close'], 20)
    df['ema_50'] = calculate_ema(df['close'], 50)
    df['vwap'] = calculate_vwap(df)
    df['bb_middle'], df['bb_upper'], df['bb_lower'] = calculate_bollinger_bands(df['close'])
    feature_cols = ['rsi', 'macd', 'atr', 'volume_spike', 'ema_20', 'vwap']
    return add_feature_lags(df, feature_cols, lags=(1, 2, 5))


def _build_feature_records(df: pd.DataFrame, symbol: str, timeframe: str) -> list[dict]:
    last_updated_at = datetime.now().isoformat()
    out = pd.DataFrame({
        'symbol': symbol,
        'timeframe': timeframe,
        'time': df['time'].dt.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'close': df['close'].round(2),
        'rsi': df['rsi'].round(2),
        'macd': df['macd'].round(2),
        'atr': df['atr'].round(2),
        'volume_spike': df['volume_spike'].fillna(False).astype(bool),
        'ema_20': df['ema_20'].round(2),
        'ema_50': df['ema_50'].round(2),
        'vwap': df['vwap'].round(2),
        'bb_upper': df['bb_upper'].round(2),
        'bb_lower': df['bb_lower'].round(2),
        'last_updated_at': last_updated_at,
    })
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
            .select('time, open, high, low, close, volume')
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
        window_df = _compute_features(window_df)

        upsert_df = window_df.iloc[:-100] if len(rows) == fetch_batch_size and len(window_df) > 120 else window_df
        records = _build_feature_records(upsert_df, symbol, timeframe)

        if records:
            db.upsert_features(records)
            total_records += len(records)
            logger.info("Upserted %s features for %s (offset=%s)", len(records), symbol, offset)

        if len(upsert_df) < len(window_df):
            window_df = window_df.iloc[-100:].copy()
        else:
            window_df = pd.DataFrame()

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
