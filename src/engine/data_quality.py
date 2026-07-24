import logging
import pandas as pd

from src.database.client import SupabaseClient
from src.engine.feature_engine import FEATURE_COLUMNS, calculate_features_for_symbol
from src.utils.time_utils import utc_now_iso

logger = logging.getLogger(__name__)


def _expected_bars_for_1m() -> int:
    # VN session rough default (can be adjusted by exchange calendar later)
    return 225


def check_data_quality(symbol: str, trading_date: str, timeframe: str = '1m') -> list[dict]:
    db = SupabaseClient()
    start = f"{trading_date} 00:00:00"
    end = f"{trading_date} 23:59:59"

    intraday_res = db.get().table('stock_intraday').select('time, close, volume').eq('symbol', symbol).eq('timeframe', timeframe).gte('time', start).lte('time', end).execute()
    feature_res = db.get().table('features').select('time').eq('symbol', symbol).eq('timeframe', timeframe).gte('time', start).lte('time', end).execute()

    intraday_df = pd.DataFrame(intraday_res.data or [])
    feature_df = pd.DataFrame(feature_res.data or [])

    logs = []
    created_at = utc_now_iso()
    expected = _expected_bars_for_1m()
    actual = len(intraday_df)
    missing = max(expected - actual, 0)

    logs.append({
        'symbol': symbol,
        'trading_date': trading_date,
        'check_type': 'intraday_count',
        'status': 'ok' if actual >= expected else 'warning',
        'message': f'intraday bars={actual}, expected~{expected}',
        'missing_count': missing,
        'expected_count': expected,
        'actual_count': actual,
        'created_at': created_at,
    })

    if not intraday_df.empty:
        null_close = int(intraday_df['close'].isna().sum()) if 'close' in intraday_df.columns else 0
        null_volume = int(intraday_df['volume'].isna().sum()) if 'volume' in intraday_df.columns else 0
        logs.append({
            'symbol': symbol,
            'trading_date': trading_date,
            'check_type': 'intraday_nulls',
            'status': 'ok' if (null_close + null_volume) == 0 else 'warning',
            'message': f'null close={null_close}, null volume={null_volume}',
            'missing_count': null_close + null_volume,
            'expected_count': 0,
            'actual_count': null_close + null_volume,
            'created_at': created_at,
        })

    if not feature_df.empty:
        merged = db.get().table('features').select(','.join(['time'] + FEATURE_COLUMNS)).eq('symbol', symbol).eq('timeframe', timeframe).gte('time', start).lte('time', end).execute()
        fdf = pd.DataFrame(merged.data or [])
        feature_nulls = int(fdf[FEATURE_COLUMNS].isna().sum().sum()) if not fdf.empty else 0
        logs.append({
            'symbol': symbol,
            'trading_date': trading_date,
            'check_type': 'feature_nulls',
            'status': 'ok' if feature_nulls == 0 else 'warning',
            'message': f'feature null cells={feature_nulls}',
            'missing_count': feature_nulls,
            'expected_count': 0,
            'actual_count': feature_nulls,
            'created_at': created_at,
        })

    db._upsert_in_batches('data_quality_logs', logs, batch_size=500)
    return logs


def recompute_features_for_day(symbol: str, trading_date: str, timeframe: str = '1m') -> int:
    """Recompute features for a symbol and date when data becomes complete."""
    db = SupabaseClient()
    start = f"{trading_date} 00:00:00"
    end = f"{trading_date} 23:59:59"

    result = db.get().table('stock_intraday').select('time, open, high, low, close, volume, value').eq('symbol', symbol).eq('timeframe', timeframe).gte('time', start).lte('time', end).order('time', desc=False).execute()
    rows = result.data or []
    if not rows:
        logger.warning('No intraday rows for %s %s', symbol, trading_date)
        return 0

    # Reuse full symbol recompute for consistency; safe upsert updates nulls when enough data.
    return calculate_features_for_symbol(symbol=symbol, timeframe=timeframe)
