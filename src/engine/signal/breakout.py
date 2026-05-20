# src/engine/signal/breakout.py
import pandas as pd
from .base import SignalStrategy

class BreakoutStrategy(SignalStrategy):
    def get_signal_type(self):
        return "BREAKOUT"

    def evaluate(self, row):
        close = row.get('close')
        bb_upper = row.get('bb_upper')
        vol_spike = row.get('volume_spike')
        
        if any(pd.isna(x) for x in [close, bb_upper]):
            return None
        
        if close > bb_upper and vol_spike:
            score = 0
            score += 2 if vol_spike else 0
            score += 1 if close > bb_upper else 0
            score += 1 if close > row.get('ema_20', 0) else 0
            
            if score >= 4:
                return {
                    'type': self.get_signal_type(),
                    'score': score,
                    'reason': {'breakout': True, 'volume_spike': vol_spike},
                    'suggestion': 'Breakout khỏi dải trên, có thể tiếp tục tăng'
                }
        return None