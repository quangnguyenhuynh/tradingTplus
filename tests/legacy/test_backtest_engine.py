import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engine.backtest_engine import BacktestConfig, run_backtest


def _feature(symbol, minute, close):
    return {
        "symbol": symbol,
        "timeframe": "1m",
        "time": f"2026-06-18T09:{minute:02d}:00Z",
        "close": close,
    }


def test_run_backtest_calculates_long_trade_metrics():
    features = [_feature("SSI", minute, close) for minute, close in enumerate([100, 101, 103, 104, 105], start=15)]
    signals = [{"symbol": "SSI", "timeframe": "1m", "time": "2026-06-18T09:15:00Z", "signal_type": "BUY", "score": 80}]

    result = run_backtest(features, signals, BacktestConfig(initial_capital=1_000_000, holding_bars=2, fee_pct=0.001))

    assert result["trade_count"] == 1
    assert result["win_count"] == 1
    assert result["win_rate_pct"] == 100
    assert result["trades"][0]["entry_price"] == 100
    assert result["trades"][0]["exit_price"] == 103
    assert result["total_pnl"] == pytest.approx(28_000)


def test_run_backtest_supports_short_signals_and_score_filter():
    features = [_feature("SSI", minute, close) for minute, close in enumerate([100, 98, 95, 90], start=15)]
    signals = [
        {"symbol": "SSI", "timeframe": "1m", "time": "2026-06-18T09:15:00Z", "signal_type": "BUY", "score": 10},
        {"symbol": "SSI", "timeframe": "1m", "time": "2026-06-18T09:16:00Z", "signal_type": "SELL", "score": 90},
    ]

    result = run_backtest(features, signals, BacktestConfig(initial_capital=1_000_000, holding_bars=2, fee_pct=0, min_score=50))

    assert result["trade_count"] == 1
    assert result["trades"][0]["direction"] == "short"
    assert result["trades"][0]["entry_price"] == 98
    assert result["trades"][0]["exit_price"] == 90
    assert result["total_pnl"] == pytest.approx((8 / 98) * 1_000_000)


def test_run_backtest_returns_empty_summary_without_inputs():
    result = run_backtest([], [], BacktestConfig(initial_capital=1_000_000))

    assert result["trade_count"] == 0
    assert result["final_capital"] == 1_000_000
    assert result["total_pnl"] == 0


def test_backtest_entry_never_uses_future_or_stale_intraday_feature():
    features = [
        _feature("SSI", 15, 100),
        _feature("SSI", 20, 105),
        _feature("SSI", 21, 106),
    ]
    stale_signal = [{"symbol": "SSI", "timeframe": "1m", "time": "2026-06-18T09:19:00Z", "signal_type": "BUY"}]

    stale = run_backtest(features, stale_signal, BacktestConfig(holding_bars=1, fee_pct=0))

    assert stale["trade_count"] == 0  # 09:20 is future; 09:15 exceeds two-minute staleness.
