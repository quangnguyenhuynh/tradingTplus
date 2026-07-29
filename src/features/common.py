import pandas as pd

from src.intraday_value import calculate_trade_value

SUPPORTED_TIMEFRAMES = {'1m', '5m', '15m', '60m', '1d'}
INTRADAY_TIMEFRAMES = {'1m', '5m', '15m', '60m'}

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


def _fill_missing_value_from_ohlcv(df: pd.DataFrame) -> pd.Series:
    values = df['value'].copy()
    missing_mask = values.isna()
    if missing_mask.any():
        values.loc[missing_mask] = df.loc[missing_mask].apply(
            lambda row: calculate_trade_value(row['close'], row['volume']),
            axis=1,
        )
    return pd.to_numeric(values, errors='coerce')


def safe_div(numerator, denominator, index) -> pd.Series:
    numerator_s = numerator.reindex(index) if isinstance(numerator, pd.Series) else pd.Series(numerator, index=index)
    denominator_s = denominator.reindex(index) if isinstance(denominator, pd.Series) else pd.Series(denominator, index=index)
    denominator_s = denominator_s.mask(denominator_s == 0)
    result = numerator_s / denominator_s
    return result.replace([float('inf'), float('-inf')], pd.NA)


def nullable_comparison(left, right, op) -> pd.Series:
    left_s = pd.Series(left, copy=False)
    right_s = pd.Series(right, index=left_s.index, copy=False)
    valid = left_s.notna() & right_s.notna()
    result = pd.Series(pd.NA, index=left_s.index, dtype="boolean")
    result.loc[valid] = op(left_s.loc[valid], right_s.loc[valid]).astype(bool)
    return result


def _prepare_ohlcv(df: pd.DataFrame, required_cols=None) -> pd.DataFrame:
    required_cols = required_cols or ['time', 'open', 'high', 'low', 'close', 'volume', 'value']
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    out = df[required_cols].copy()
    out['time'] = pd.to_datetime(out['time'], errors='coerce', utc=True)
    if out['time'].isna().any():
        raise ValueError(f"Invalid time values found: {int(out['time'].isna().sum())} rows")
    for col in ['open', 'high', 'low', 'close', 'volume', 'value']:
        out[col] = pd.to_numeric(out[col], errors='coerce')
    out['value'] = _fill_missing_value_from_ohlcv(out)
    out = out.sort_values('time').drop_duplicates(subset=['time'], keep='last')
    return out.reset_index(drop=True)


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


def _build_daily_prev_close_map(daily_df: pd.DataFrame | None) -> dict:
    if daily_df is None or daily_df.empty:
        return {}
    required_cols = {'trading_date', 'close_price'}
    missing_cols = required_cols - set(daily_df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns for daily previous close: {sorted(missing_cols)}")
    daily = daily_df[['trading_date', 'close_price']].copy()
    daily['trading_date'] = pd.to_datetime(daily['trading_date'], errors='coerce').dt.date
    daily['close_price'] = pd.to_numeric(daily['close_price'], errors='coerce')
    daily = daily.dropna(subset=['trading_date', 'close_price']).sort_values('trading_date')
    daily = daily.drop_duplicates(subset=['trading_date'], keep='last')
    daily['prev_close'] = daily['close_price'].shift(1)
    return daily.set_index('trading_date')['prev_close'].dropna().to_dict()


def _build_daily_open_map(daily_df: pd.DataFrame | None) -> dict:
    if daily_df is None or daily_df.empty or not {'trading_date', 'open_price'}.issubset(daily_df.columns):
        return {}
    daily = daily_df[['trading_date', 'open_price']].copy()
    daily['trading_date'] = pd.to_datetime(daily['trading_date'], errors='coerce').dt.date
    daily['open_price'] = pd.to_numeric(daily['open_price'], errors='coerce').where(lambda s: s > 0)
    return daily.dropna().drop_duplicates('trading_date', keep='last').set_index('trading_date')['open_price'].to_dict()


def _session_bucket_baseline(out: pd.DataFrame, date_key, column: str) -> pd.Series:
    local = out['time'].dt.tz_convert('Asia/Ho_Chi_Minh')
    session = (local.dt.hour >= 12).astype(int)
    bucket_time = local.dt.strftime('%H:%M')
    keys = [session, bucket_time]
    return out.groupby(keys, sort=False)[column].transform(lambda values: values.shift(1).rolling(20, min_periods=20).mean())


def _add_common_features(out: pd.DataFrame, date_key, daily_df: pd.DataFrame | None, reset_volume_by_day: bool) -> pd.DataFrame:
    if reset_volume_by_day:
        open_map = _build_daily_open_map(daily_df)
        official_opens = pd.Series([open_map.get(d) for d in date_key], index=out.index)
        out['return_from_open'] = safe_div(out['close'], official_opens, out.index) - 1
    else:
        out['return_from_open'] = safe_div(out['close'], out['open'], out.index) - 1
    prev_close_map = _build_daily_prev_close_map(daily_df)
    prev_close_values = [prev_close_map.get(trading_date) for trading_date in date_key]
    out['return_from_prev_close'] = safe_div(out['close'], pd.Series(prev_close_values, index=out.index), out.index) - 1
    out['ema9'] = out['close'].ewm(span=9, adjust=False, min_periods=9).mean()
    out['ema20'] = out['close'].ewm(span=20, adjust=False, min_periods=20).mean()
    out['ema50'] = out['close'].ewm(span=50, adjust=False, min_periods=50).mean()
    out['ema9_above_ema20'] = nullable_comparison(out['ema9'], out['ema20'], lambda a, b: a > b)
    out['ema20_above_ema50'] = nullable_comparison(out['ema20'], out['ema50'], lambda a, b: a > b)
    out['rsi14'] = calculate_rsi(out['close'])
    out['macd'], out['macd_signal'], out['macd_histogram'] = calculate_macd(out['close'])
    if reset_volume_by_day:
        out['volume_ma20'] = _session_bucket_baseline(out, date_key, 'volume')
        out['value_ma20'] = _session_bucket_baseline(out, date_key, 'value')
    else:
        out['volume_ma20'] = out['volume'].rolling(20).mean()
        out['value_ma20'] = out['value'].rolling(20).mean()
    out['volume_ratio'] = safe_div(out['volume'], out['volume_ma20'], out.index)
    out['value_ratio'] = safe_div(out['value'], out['value_ma20'], out.index)
    out['high_20_bars'] = out['high'].shift(1).rolling(20).max()
    out['low_20_bars'] = out['low'].shift(1).rolling(20).min()
    out['close_above_high_20'] = nullable_comparison(out['close'], out['high_20_bars'], lambda a, b: a > b)
    out['close_below_low_20'] = nullable_comparison(out['close'], out['low_20_bars'], lambda a, b: a < b)
    out['candle_range'] = out['high'] - out['low']
    out['candle_body'] = out['close'] - out['open']
    out['candle_body_pct'] = safe_div(out['candle_body'], out['open'], out.index)
    out['close_position_in_candle'] = safe_div(out['close'] - out['low'], out['candle_range'], out.index)
    return out
