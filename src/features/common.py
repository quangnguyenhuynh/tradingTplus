import pandas as pd

from src.intraday_value import calculate_trade_value

SUPPORTED_TIMEFRAMES = {'1m', '5m', '15m', '60m', '1d'}
INTRADAY_TIMEFRAMES = {'1m', '5m', '15m', '60m'}
RETURN_TOLERANCE_MINUTES = {1: 1, 5: 2, 15: 2}

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


def aggregate_timeframe(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Aggregate stock_intraday 1m OHLCV rows to an intraday feature timeframe.

    The aggregation never crosses Vietnam trading dates or the lunch break.
    Daily (1d) features are sourced from stock_daily and are intentionally not
    supported here.
    """
    if timeframe not in INTRADAY_TIMEFRAMES:
        raise ValueError(f"Unsupported intraday timeframe: {timeframe}. Supported: {sorted(INTRADAY_TIMEFRAMES)}")
    if df.empty:
        return df.copy()
    out = _prepare_ohlcv(df)
    if timeframe == '1m':
        return out

    rule = {'5m': '5min', '15m': '15min', '60m': '60min'}[timeframe]
    local = out.copy()
    local['time'] = local['time'].dt.tz_convert('Asia/Ho_Chi_Minh')
    local = local.set_index('time')
    pieces = []
    for (_trading_date, session), part in local.groupby([local.index.date, (local.index.hour >= 12)], sort=True):
        aggregated = (
            part.resample(rule, label='left', closed='left')
            .agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum', 'value': 'sum'})
            .dropna(subset=['open', 'high', 'low', 'close'])
            .reset_index()
        )
        pieces.append(aggregated)
    if not pieces:
        return out.iloc[0:0].reset_index(drop=True)
    result = pd.concat(pieces, ignore_index=True)
    result['time'] = pd.to_datetime(result['time']).dt.tz_convert('UTC')
    return result.sort_values('time').reset_index(drop=True)


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


def _time_aware_return(out: pd.DataFrame, horizon_minutes: int) -> pd.Series:
    """Return versus the latest observed candle at/before the wall-clock target.

    References are restricted to the same Vietnam trading date and morning or
    afternoon session. A bounded tolerance prevents stale prices from filling
    no-trade/source gaps indefinitely. The backward lookup can never look ahead.
    """
    tolerance = pd.Timedelta(minutes=RETURN_TOLERANCE_MINUTES[horizon_minutes])
    target_delta = pd.Timedelta(minutes=horizon_minutes)
    local_time = out['time'].dt.tz_convert('Asia/Ho_Chi_Minh')
    date_keys = local_time.dt.date
    session_keys = (local_time.dt.hour >= 12).astype(int)
    result = pd.Series(float('nan'), index=out.index, dtype='float64')

    for indexes in out.groupby([date_keys, session_keys], sort=False).groups.values():
        positions = list(indexes)
        times = out.loc[positions, 'time'].reset_index(drop=True)
        closes = out.loc[positions, 'close'].reset_index(drop=True)
        targets = times - target_delta
        reference_positions = times.searchsorted(targets, side='right') - 1
        valid = reference_positions >= 0
        if valid.any():
            candidate_rows = reference_positions[valid]
            candidate_times = times.iloc[candidate_rows].reset_index(drop=True)
            valid_targets = targets[valid].reset_index(drop=True)
            within_tolerance = (valid_targets - candidate_times) <= tolerance
            output_positions = pd.Series(positions)[valid].reset_index(drop=True)[within_tolerance]
            reference_closes = closes.iloc[candidate_rows].reset_index(drop=True)[within_tolerance]
            current_closes = closes[pd.Series(valid).to_numpy()].reset_index(drop=True)[within_tolerance]
            result.loc[output_positions.to_list()] = (
                current_closes.to_numpy() / reference_closes.to_numpy() - 1
            )
    return result


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


def compute_intraday_features(df: pd.DataFrame, timeframe: str, daily_df: pd.DataFrame | None = None) -> pd.DataFrame:
    if timeframe not in INTRADAY_TIMEFRAMES:
        raise ValueError(f"Unsupported intraday timeframe: {timeframe}")
    if df.empty:
        return df.copy()
    out = _prepare_ohlcv(df)
    if out['time'].duplicated().any():
        raise ValueError("Duplicate time detected in feature input")
    date_key = out['time'].dt.tz_convert('Asia/Ho_Chi_Minh').dt.date
    out['return_1m'] = _time_aware_return(out, 1) if timeframe == '1m' else pd.NA
    out['return_5m'] = _time_aware_return(out, 5) if timeframe in {'1m', '5m'} else pd.NA
    out['return_15m'] = _time_aware_return(out, 15) if timeframe in {'1m', '5m', '15m'} else pd.NA
    out = _add_common_features(out, date_key, daily_df, reset_volume_by_day=True)
    cum_value = out.groupby(date_key)['value'].cumsum()
    cum_volume = out.groupby(date_key)['volume'].cumsum()
    out['vwap_intraday'] = safe_div(cum_value, cum_volume, out.index)
    out['close_above_vwap'] = nullable_comparison(out['close'], out['vwap_intraday'], lambda a, b: a > b)
    out['distance_to_vwap_pct'] = safe_div(out['close'] - out['vwap_intraday'], out['vwap_intraday'], out.index)
    return out


def _daily_to_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    required = ['trading_date', 'open_price', 'highest_price', 'lowest_price', 'close_price']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns for daily feature calculation: {missing}")
    out = pd.DataFrame({
        'time': pd.to_datetime(df['trading_date'], errors='coerce').dt.tz_localize('Asia/Ho_Chi_Minh').dt.tz_convert('UTC'),
        'open': pd.to_numeric(df['open_price'], errors='coerce'),
        'high': pd.to_numeric(df['highest_price'], errors='coerce'),
        'low': pd.to_numeric(df['lowest_price'], errors='coerce'),
        'close': pd.to_numeric(df['close_price'], errors='coerce'),
        'volume': pd.to_numeric(df.get('total_traded_vol', df.get('total_match_vol')), errors='coerce'),
        'value': pd.to_numeric(df.get('total_traded_value', df.get('total_match_val')), errors='coerce'),
    })
    out = out.dropna(subset=['time']).sort_values('time').drop_duplicates(subset=['time'], keep='last').reset_index(drop=True)
    return out


def compute_daily_features(daily_df: pd.DataFrame) -> pd.DataFrame:
    if daily_df.empty:
        return pd.DataFrame()
    out = _daily_to_ohlcv(daily_df)
    date_key = out['time'].dt.tz_convert('Asia/Ho_Chi_Minh').dt.date
    out['return_1m'] = pd.NA
    out['return_5m'] = pd.NA
    out['return_15m'] = pd.NA
    out = _add_common_features(out, date_key, daily_df, reset_volume_by_day=False)
    out['vwap_intraday'] = pd.NA
    out['close_above_vwap'] = pd.NA
    out['distance_to_vwap_pct'] = pd.NA
    return out


def compute_feature_dataframe(df: pd.DataFrame, daily_df: pd.DataFrame | None = None, timeframe: str = '1m') -> pd.DataFrame:
    """Backward-compatible wrapper. New code should call specific functions."""
    if timeframe == '1d':
        return compute_daily_features(df)
    return compute_intraday_features(df, timeframe=timeframe, daily_df=daily_df)
