import pandas as pd


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta.where(delta < 0, 0.0))
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    rsi = rsi.mask((avg_gain == 0) & (avg_loss > 0), 0.0)
    rsi = rsi.mask((avg_gain == 0) & (avg_loss == 0), pd.NA)
    return rsi


def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = prices.ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = prices.ewm(span=slow, adjust=False, min_periods=slow).mean()
    macd_line = ema_fast - ema_slow
    macd_signal = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    macd_hist = macd_line - macd_signal
    return macd_line, macd_signal, macd_hist


def compute_feature_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    required_cols = ['time', 'open', 'high', 'low', 'close', 'volume', 'value']
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns for feature calculation: {missing_cols}")

    out = df.copy()
    out['time'] = pd.to_datetime(out['time'], errors='coerce', utc=True)
    invalid_time_mask = out['time'].isna()
    if invalid_time_mask.any():
        raise ValueError(f"Invalid time values found: {int(invalid_time_mask.sum())} rows")

    out = out.sort_values('time').copy()
    if out['time'].duplicated().any():
        dup_count = int(out['time'].duplicated().sum())
        raise ValueError(f"Duplicate time detected in feature input: {dup_count} rows")

    numeric_price_cols = ['open', 'high', 'low', 'close', 'volume', 'value']
    for col in numeric_price_cols:
        out[col] = pd.to_numeric(out[col], errors='coerce')

    def _safe_div(numerator, denominator) -> pd.Series:
        numerator_s = numerator.reindex(out.index) if isinstance(numerator, pd.Series) else pd.Series(numerator, index=out.index)
        denominator_s = denominator.reindex(out.index) if isinstance(denominator, pd.Series) else pd.Series(denominator, index=out.index)
        denominator_s = denominator_s.mask(denominator_s == 0)
        result = numerator_s / denominator_s
        return result.replace([float('inf'), float('-inf')], pd.NA)

    trading_time = out['time'].dt.tz_convert('Asia/Ho_Chi_Minh')
    date_key = trading_time.dt.date

    # Session-reset returns (computed independently per trading date).
    out['return_1m'] = out.groupby(date_key)['close'].pct_change(1)
    out['return_5m'] = out.groupby(date_key)['close'].pct_change(5)
    out['return_15m'] = out.groupby(date_key)['close'].pct_change(15)

    session_open = out.groupby(date_key)['open'].transform('first')
    out['return_from_open'] = _safe_div(out['close'], session_open) - 1

    # Previous-session close return (same previous daily close for all bars in session).
    session_close = out.groupby(date_key)['close'].transform('last')
    prev_session_close_map = session_close.groupby(date_key).first().shift(1)
    prev_session_close = date_key.map(prev_session_close_map)
    out['return_from_prev_close'] = _safe_div(out['close'], pd.Series(prev_session_close, index=out.index)) - 1

    # Continuous intraday trend features (do not reset by session).
    out['ema9'] = out['close'].ewm(span=9, adjust=False, min_periods=9).mean()
    out['ema20'] = out['close'].ewm(span=20, adjust=False, min_periods=20).mean()
    out['ema50'] = out['close'].ewm(span=50, adjust=False, min_periods=50).mean()
    out['ema9_above_ema20'] = out['ema9'] > out['ema20']
    out['ema20_above_ema50'] = out['ema20'] > out['ema50']

    # Continuous intraday momentum features (do not reset by session).
    out['rsi14'] = calculate_rsi(out['close'], period=14)
    out['macd'], out['macd_signal'], out['macd_histogram'] = calculate_macd(out['close'])

    # Session-reset volume features (no cross-date leakage).
    out['volume_ma20'] = out.groupby(date_key)['volume'].transform(lambda s: s.rolling(20).mean())
    out['volume_ratio'] = _safe_div(out['volume'], out['volume_ma20'])
    out['value_ma20'] = out.groupby(date_key)['value'].transform(lambda s: s.rolling(20).mean())
    out['value_ratio'] = _safe_div(out['value'], out['value_ma20'])

    # Session-reset breakout features with shift(1) to avoid lookahead.
    out['high_20_bars'] = out.groupby(date_key)['high'].transform(lambda s: s.shift(1).rolling(20).max())
    out['low_20_bars'] = out.groupby(date_key)['low'].transform(lambda s: s.shift(1).rolling(20).min())
    out['close_above_high_20'] = out['close'] > out['high_20_bars']
    out['close_below_low_20'] = out['close'] < out['low_20_bars']

    # Session-reset VWAP features.
    cum_value = out.groupby(date_key)['value'].cumsum()
    cum_volume = out.groupby(date_key)['volume'].cumsum()
    out['vwap_intraday'] = _safe_div(cum_value, cum_volume)
    out['close_above_vwap'] = out['close'] > out['vwap_intraday']
    out['distance_to_vwap_pct'] = _safe_div(out['close'] - out['vwap_intraday'], out['vwap_intraday'])

    # Session-independent candle geometry per bar.
    out['candle_range'] = out['high'] - out['low']
    out['candle_body'] = out['close'] - out['open']
    out['candle_body_pct'] = _safe_div(out['candle_body'], out['open'])
    out['close_position_in_candle'] = _safe_div(out['close'] - out['low'], out['candle_range'])

    return out
