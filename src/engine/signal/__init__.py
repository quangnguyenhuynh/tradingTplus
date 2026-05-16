# src/engine/signal/__init__.py
from .reversal import ReversalStrategy
from .breakout import BreakoutStrategy
from .trend import TrendStrategy

__all__ = ['ReversalStrategy', 'BreakoutStrategy', 'TrendStrategy']