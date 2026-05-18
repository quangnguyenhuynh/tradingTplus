# src/engine/signal_engine.py
import pandas as pd
from datetime import datetime, time
from src.database.client import SupabaseClient
from src.engine.signal.reversal import ReversalStrategy
from src.engine.signal.breakout import BreakoutStrategy
from src.engine.signal.trend import TrendStrategy

CHECK_TIMES = [time(9,45), time(10,30), time(13,45), time(14,30)]

def run_signal_engine(target_date=None):
    db = SupabaseClient()
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")
    print(f"🚦 Signal engine cho {target_date}")

    # Lấy features
    result = db.get().table('features')\
        .select('symbol, time, close, rsi, ema_20, ema_50, bb_upper, volume_spike')\
        .gte('time', f"{target_date} 00:00:00")\
        .lte('time', f"{target_date} 23:59:59")\
        .execute()
    df = pd.DataFrame(result.data)
    if df.empty:
        print("   ⚠️ Không có features")
        return

    df['time'] = pd.to_datetime(df['time'])
    strategies = [ReversalStrategy(), BreakoutStrategy(), TrendStrategy()]
    signals = []

    for check_time in CHECK_TIMES:
        bucket_dt = datetime.strptime(f"{target_date} {check_time.strftime('%H:%M')}:00", "%Y-%m-%d %H:%M:%S")
        for symbol in df['symbol'].unique():
            symbol_df = df[df['symbol'] == symbol].copy()
            candidate = symbol_df[symbol_df['time'] <= bucket_dt].sort_values('time', ascending=False)
            if candidate.empty:
                continue
            row = candidate.iloc[0]
            for strategy in strategies:
                res = strategy.evaluate(row)
                if res:
                    signals.append({
                        'symbol': symbol,
                        'timeframe': '1m',
                        'time': row['time'].isoformat(),
                        'signal_type': res['type'],
                        'score': res['score'],
                        'reason': res['reason'],
                        'suggestion': res['suggestion'],
                        'bucket_time': check_time.strftime("%H:%M:%S")
                    })

    if signals:
        for s in signals:
            db.get().table('trading_signals').upsert(s, on_conflict='symbol,signal_type,bucket_time').execute()
        print(f"   ✅ Đã lưu {len(signals)} signals")
    else:
        print("   ⚪ Không có signal")

if __name__ == "__main__":
    run_signal_engine()