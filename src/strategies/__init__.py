"""Versioned, explainable two-stage trading strategies."""

from .registry import get_strategy, list_strategies

__all__ = ["get_strategy", "list_strategies"]
