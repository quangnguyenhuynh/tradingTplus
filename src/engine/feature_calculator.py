import pandas as pd


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta.where(delta < 0, 0.0))
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    macd_signal = macd_line.ewm(span=signal, adjust=False).mean()
    macd_hist = macd_line - macd_signal
    return macd_line, macd_signal, macd_hist


def compute_feature_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = df.sort_values('time').copy()
    out['time'] = pd.to_datetime(out['time'], errors='coerce')

    numeric_price_cols = ['open', 'high', 'low', 'close', 'volume', 'value']
    for col in numeric_price_cols:
        out[col] = pd.to_numeric(out[col], errors='coerce')

    # return
    out['return_1m'] = out['close'].pct_change(1)
    out['return_5m'] = out['close'].pct_change(5)
    out['return_15m'] = out['close'].pct_change(15)
    session_open = out.groupby(out['time'].dt.date)['open'].transform('first')
    prev_close = out['close'].shift(1)
    out['return_from_open'] = (out['close'] / session_open) - 1
    out['return_from_prev_close'] = (out['close'] / prev_close) - 1

    # trend
    out['ema9'] = out['close'].ewm(span=9, adjust=False).mean()
    out['ema20'] = out['close'].ewm(span=20, adjust=False).mean()
    out['ema50'] = out['close'].ewm(span=50, adjust=False).mean()
    out['ema9_above_ema20'] = out['ema9'] > out['ema20']
    out['ema20_above_ema50'] = out['ema20'] > out['ema50']

    # momentum
    out['rsi14'] = calculate_rsi(out['close'], period=14)
    out['macd'], out['macd_signal'], out['macd_histogram'] = calculate_macd(out['close'])

    # volume
    out['volume_ma20'] = out['volume'].rolling(20).mean()
    out['volume_ratio'] = out['volume'] / out['volume_ma20']
    out['value_ma20'] = out['value'].rolling(20).mean()
    out['value_ratio'] = out['value'] / out['value_ma20']

    # breakout
    out['high_20_bars'] = out['high'].shift(1).rolling(20).max()
    out['low_20_bars'] = out['low'].shift(1).rolling(20).min()
    out['close_above_high_20'] = out['close'] > out['high_20_bars']
    out['close_below_low_20'] = out['close'] < out['low_20_bars']

    # vwap (intraday)
    date_key = out['time'].dt.date
    cum_value = out.groupby(date_key)['value'].cumsum()
    cum_volume = out.groupby(date_key)['volume'].cumsum()
    out['vwap_intraday'] = cum_value / cum_volume.replace(0, float('nan'))
    out['close_above_vwap'] = out['close'] > out['vwap_intraday']
    out['distance_to_vwap_pct'] = (out['close'] - out['vwap_intraday']) / out['vwap_intraday']

    # candle
    out['candle_range'] = out['high'] - out['low']
    out['candle_body'] = out['close'] - out['open']
    out['candle_body_pct'] = out['candle_body'] / out['open']
    out['close_position_in_candle'] = (out['close'] - out['low']) / out['candle_range'].replace(0, pd.NA)

    return out
