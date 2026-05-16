# src/engine/signal/trend.py
import pandas as pd
from .base import SignalStrategy

class TrendStrategy(SignalStrategy):
    def get_signal_type(self):
        return "TREND"

    def evaluate(self, row):
        ema20 = row.get('ema_20')
        ema50 = row.get('ema_50')
        close = row.get('close')
        
        if any(pd.isna(x) for x in [ema20, ema50, close]):
            return None
        
        if ema20 > ema50 and close > ema20:
            score = 0
            score += 1 if ema20 > ema50 else 0
            score += 1 if close > ema20 else 0
            
            if score >= 2:
                return {
                    'type': self.get_signal_type(),
                    'score': score,
                    'reason': {'trend_up': True, 'ema20_above_ema50': True},
                    'suggestion': 'Xu hướng tăng'
                }
        return None