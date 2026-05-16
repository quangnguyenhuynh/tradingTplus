# src/engine/signal/reversal.py
import pandas as pd
from .base import SignalStrategy

class ReversalStrategy(SignalStrategy):
    def get_signal_type(self):
        return "REVERSAL"

    def evaluate(self, row):
        rsi = row.get('rsi')
        vol_spike = row.get('volume_spike')
        close = row.get('close')
        ema20 = row.get('ema_20')
        ema50 = row.get('ema_50')
        
        if any(pd.isna(x) for x in [rsi, close, ema20, ema50]):
            return None
        
        if rsi < 30 and vol_spike and close > ema20:
            score = 0
            score += 3 if rsi < 25 else 2
            score += 2 if vol_spike else 0
            score += 1 if close > ema20 else 0
            score += 1 if close > ema50 else 0
            
            if score >= 5:
                return {
                    'type': self.get_signal_type(),
                    'score': score,
                    'reason': {'rsi_low': True, 'volume_spike': vol_spike},
                    'suggestion': 'Xem xét mua khi giá vượt kháng cự'
                }
        return None