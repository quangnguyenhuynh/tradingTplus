# src/engine/feature_engine.py
import pandas as pd
import numpy as np
from src.database.client import SupabaseClient
from datetime import datetime

# ============================================
# LEVEL 1: CHỈ BÁO CƠ BẢN
# ============================================

def calculate_rsi_wilder(prices, period=14):
    """
    RSI Wilder - Chuẩn sử dụng trong trading
    Công thức: RSI = 100 - 100 / (1 + RS)
    Với RS = EMA(gain) / EMA(loss), alpha = 1/period
    """
    delta = prices.diff()
    
    gain = delta.where(delta > 0, 0)
    loss = (-delta.where(delta < 0, 0))
    
    # Wilder Smoothing (EMA với alpha = 1/period)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """
    MACD (Moving Average Convergence Divergence)
    Trả về: macd_line, macd_signal, macd_histogram
    """
    exp_fast = prices.ewm(span=fast, adjust=False).mean()
    exp_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = exp_fast - exp_slow
    macd_signal = macd_line.ewm(span=signal, adjust=False).mean()
    macd_histogram = macd_line - macd_signal
    return macd_line, macd_signal, macd_histogram

def calculate_atr(df, period=14):
    """
    ATR (Average True Range) - Đo độ biến động
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    high_low = high - low
    high_close = abs(high - close.shift())
    low_close = abs(low - close.shift())
    
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def calculate_volume_spike(volume, window=20, std_mult=2.0):
    """
    Phát hiện volume spike (đột biến khối lượng)
    Spike khi volume > mean + std_mult * std
    """
    mean = volume.rolling(window=window).mean()
    std = volume.rolling(window=window).std()
    spike = volume > (mean + std_mult * std)
    return spike.fillna(False)

# ============================================
# LEVEL 2: CHỈ BÁO NÂNG CAO
# ============================================

def calculate_ema(prices, period=20):
    """EMA (Exponential Moving Average)"""
    return prices.ewm(span=period, adjust=False).mean()

def calculate_vwap(df):
    """
    VWAP (Volume Weighted Average Price)
    VWAP = cumulative(price * volume) / cumulative(volume)
    """
    df = df.copy()
    df['price_vol'] = df['close'] * df['volume']
    df['cum_price_vol'] = df['price_vol'].cumsum()
    df['cum_volume'] = df['volume'].cumsum()
    vwap = df['cum_price_vol'] / df['cum_volume']
    return vwap

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """
    Bollinger Bands
    Trả về: middle_band, upper_band, lower_band
    """
    middle = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return middle, upper, lower

# ============================================
# LEVEL 3: FEATURE LAG CHO ML
# ============================================

def add_feature_lags(df, columns, lags=[1, 2, 5]):
    """Thêm các cột lag cho feature (dùng cho ML)"""
    for col in columns:
        for lag in lags:
            df[f'{col}_lag{lag}'] = df[col].shift(lag)
    return df

# ============================================
# HÀM CHÍNH: TÍNH FEATURES CHO 1 SYMBOL
# ============================================

def calculate_features_for_symbol(symbol, timeframe='1m'):
    """Tính toàn bộ features cho 1 symbol"""
    db = SupabaseClient()
    
    print(f"🔧 Đang tính features cho {symbol}...")
    # Lấy tổng số dòng trước
    count_result = db.get().table('stock_intraday')\
        .select('*', count='exact')\
        .eq('symbol', symbol)\
        .eq('timeframe', timeframe)\
        .execute()
    
    total_rows = count_result.count
    print(f"   📊 Tổng số dòng cần xử lý: {total_rows}")
    # Lấy dữ liệu theo từng batch để tránh limit 1000
    all_data = []
    batch_size = 1000
    offset = 0
    while offset < total_rows:
        result = db.get().table('stock_intraday')\
            .select('time, open, high, low, close, volume')\
            .eq('symbol', symbol)\
            .eq('timeframe', timeframe)\
            .order('time', desc=False)\
            .range(offset, offset + batch_size - 1)\
            .execute()
        
        if not result.data:
            break
        
        all_data.extend(result.data)
        offset += batch_size
        print(f"   📥 Đã lấy {len(all_data)}/{total_rows} dòng...")
    
    if not all_data:
        print(f"   ⚠️ {symbol}: không có dữ liệu")
        return 0

    

    
    # Chuyển sang DataFrame
    df = pd.DataFrame(all_data)
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time')
    
    # LEVEL 1: Chỉ báo cơ bản
    df['rsi'] = calculate_rsi_wilder(df['close'])           # RSI Wilder
    df['macd'], df['macd_signal'], df['macd_histogram'] = calculate_macd(df['close'])
    df['atr'] = calculate_atr(df)
    df['volume_spike'] = calculate_volume_spike(df['volume'])
    
    # LEVEL 2: Chỉ báo nâng cao
    df['ema_20'] = calculate_ema(df['close'], 20)
    df['ema_50'] = calculate_ema(df['close'], 50)
    df['vwap'] = calculate_vwap(df)
    df['bb_middle'], df['bb_upper'], df['bb_lower'] = calculate_bollinger_bands(df['close'])
    
    # LEVEL 3: Feature lag (cho ML)
    feature_cols = ['rsi', 'macd', 'atr', 'volume_spike', 'ema_20', 'vwap']
    df = add_feature_lags(df, feature_cols, lags=[1, 2, 5])
    
    # Chuẩn bị records để upsert
    features_records = []
    for _, row in df.iterrows():
        features_records.append({
            'symbol': symbol,
            'timeframe': timeframe,
            'time': row['time'].isoformat(),
            'close': round(row['close'], 2) if not pd.isna(row['close']) else None,
            
            # Level 1
            'rsi': round(row['rsi'], 2) if not pd.isna(row['rsi']) else None,
            'macd': round(row['macd'], 2) if not pd.isna(row['macd']) else None,
            'atr': round(row['atr'], 2) if not pd.isna(row['atr']) else None,
            'volume_spike': bool(row['volume_spike']) if not pd.isna(row['volume_spike']) else False,
            
            # Level 2
            'ema_20': round(row['ema_20'], 2) if not pd.isna(row['ema_20']) else None,
            'ema_50': round(row['ema_50'], 2) if not pd.isna(row['ema_50']) else None,
            'vwap': round(row['vwap'], 2) if not pd.isna(row['vwap']) else None,
            'bb_upper': round(row['bb_upper'], 2) if not pd.isna(row['bb_upper']) else None,
            'bb_lower': round(row['bb_lower'], 2) if not pd.isna(row['bb_lower']) else None,
            
            # Level 3
            # Level 3 – Feature lags (đầy đủ)
            #'rsi_lag1': round(row['rsi_lag1'], 2) if not pd.isna(row.get('rsi_lag1')) else None,
            #'rsi_lag2': round(row['rsi_lag2'], 2) if not pd.isna(row.get('rsi_lag2')) else None,
            #'rsi_lag5': round(row['rsi_lag5'], 2) if not pd.isna(row.get('rsi_lag5')) else None,
            
           # 'macd_lag1': round(row['macd_lag1'], 2) if not pd.isna(row.get('macd_lag1')) else None,
            #'macd_lag2': round(row['macd_lag2'], 2) if not pd.isna(row.get('macd_lag2')) else None,
            #'macd_lag5': round(row['macd_lag5'], 2) if not pd.isna(row.get('macd_lag5')) else None,
            
            #'atr_lag1': round(row['atr_lag1'], 2) if not pd.isna(row.get('atr_lag1')) else None,
            #'atr_lag2': round(row['atr_lag2'], 2) if not pd.isna(row.get('atr_lag2')) else None,
            #'atr_lag5': round(row['atr_lag5'], 2) if not pd.isna(row.get('atr_lag5')) else None,
            
            #'ema_20_lag1': round(row['ema_20_lag1'], 2) if not pd.isna(row.get('ema_20_lag1')) else None,
            #'ema_20_lag2': round(row['ema_20_lag2'], 2) if not pd.isna(row.get('ema_20_lag2')) else None,
            #'ema_20_lag5': round(row['ema_20_lag5'], 2) if not pd.isna(row.get('ema_20_lag5')) else None,
            
            #'vwap_lag1': round(row['vwap_lag1'], 2) if not pd.isna(row.get('vwap_lag1')) else None,
            #'vwap_lag2': round(row['vwap_lag2'], 2) if not pd.isna(row.get('vwap_lag2')) else None,
            #'vwap_lag5': round(row['vwap_lag5'], 2) if not pd.isna(row.get('vwap_lag5')) else None,
            
            'last_updated_at': datetime.now().isoformat()
        })
    
    # Upsert vào database (batch)
    if features_records:
        db.upsert_features(features_records)
        print(f"   ✅ {symbol}: {len(features_records)} features")
    
    return len(features_records)

# ============================================
# HÀM CHẠY CHO NHIỀU SYMBOLS
# ============================================

def run_feature_engine(symbols=None):
    """Chạy feature engine cho danh sách symbols"""
    db = SupabaseClient()
    
    if symbols is None:
        result = db.get().table('symbols').select('symbol').execute()
        symbols = [row['symbol'] for row in result.data]
    
    print(f"🚀 Bắt đầu tính features cho {len(symbols)} symbols...")
    print(f"📊 Chỉ báo: RSI(Wilder), MACD, ATR, Volume Spike, EMA20/50, VWAP, BB, Feature Lags")
    
    total = 0
    for symbol in symbols:
        try:
            count = calculate_features_for_symbol(symbol)
            total += count
        except Exception as e:
            print(f"   ❌ {symbol}: {e}")
    
    print(f"\n🎉 Hoàn thành! Đã tính {total} feature records")
    return total

# ============================================
# MAIN
# ============================================
if __name__ == "__main__":
    import sys
    
    # Lấy danh sách symbol từ command line hoặc dùng mặc định
    if len(sys.argv) > 1:
        symbols = sys.argv[1:]
    else:
        symbols = ['SSI', 'SHB', 'HPG', 'FPT']
    
    print(f"📋 Symbols: {symbols}")
    run_feature_engine(symbols)