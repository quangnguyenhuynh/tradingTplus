from pathlib import Path

from src.backtest.execution import estimate_entry
from src.backtest.approval import review_strategy
from src.backtest.outcome import map_outcomes
from src.backtest.replay import replay_strategy
from src.strategies.registry import get_strategy


def test_entry_and_outcomes_keep_missing_and_use_sessions():
    assert estimate_entry([], "2026-07-02T02:30:00Z")["entry_status"] == "missing"
    rows = [{"trading_date": day, "close_price": close} for day, close in [("2026-07-03", 11), ("2026-07-06", 12), ("2026-07-07", 13), ("2026-07-08", 14)]]
    result = map_outcomes(rows, "2026-07-02", 10)
    assert result["h1_session"] == "2026-07-03" and result["h3_session"] == "2026-07-07"
    assert result["h5_status"] == "missing"


def test_replay_runs_both_stages():
    strategy = get_strategy("BREAKOUT_V1")
    daily = {"symbol": "SSI", "timeframe": "1d", "time": "2026-07-01T07:00:00Z", "close_above_high_20": True, "volume_ratio": 1.3}
    feature = {"symbol": "SSI", "time": "2026-07-02T02:30:00Z", "close_above_vwap": True, "rsi14": 55, "closed": True}
    sessions = [{"session": "2026-07-01", "daily_feature": daily}, {"session": "2026-07-02", "daily_feature": {**daily, "time": "2026-07-02T07:00:00Z"}, "scans": {"09:30": {"decision_time": "2026-07-02T02:30:00Z", "features": {tf: [{**feature, "timeframe": tf}] for tf in ("15m", "60m")}}}, "candles_1m": [{"timeframe": "1m", "time": "2026-07-02T02:31:00Z", "open": 10}], "daily_outcomes": [{"trading_date": f"2026-07-0{day}", "close_price": 10 + day} for day in range(3, 8)]}]
    result = replay_strategy(strategy, sessions)
    assert result["mode"] == "daily_intraday" and len(result["signals"]) == 1
    assert result["signals"][0]["h5_status"] == "available"


def test_migration_contract():
    sql = Path("migrations/20260804_create_strategy_signal_backtest.sql").read_text().lower()
    for table in ("strategies", "strategy_setups", "signals", "backtest_runs", "backtest_signals", "strategy_reviews"):
        assert f"create table if not exists public.{table}" in sql
    assert sql.count("unique (") >= 5 and "verification" in sql and "rollback guidance" in sql
    assert "create table if not exists public.trading_signals" not in sql
    assert "create table if not exists public.backtest_data" not in sql


def test_daily_only_evidence_cannot_approve():
    class Repo:
        def get_backtest_run(self, _):
            return {"strategy_code": "BREAKOUT_V1", "strategy_version": 1,
                    "config_hash": get_strategy("BREAKOUT_V1").config_hash,
                    "status": "completed", "mode": "daily_only", "metrics": {"sample_size": 1}}

    import pytest
    with pytest.raises(ValueError, match="two-stage"):
        review_strategy(Repo(), get_strategy("BREAKOUT_V1"), "run-1", "approve", "owner", "reviewed")
