import pytest

from src.signals.daily_setup import create_daily_setup
from src.signals.scanner import scan_candidate
from src.strategies.registry import get_strategy


class Repo:
    def __init__(self, status="draft"):
        self.status, self.setups, self.signals = status, {}, {}
    def strategy_status(self, *_): return self.status
    def upsert_setup(self, record):
        key = tuple(record[k] for k in ("strategy_code", "strategy_version", "config_hash", "symbol", "setup_date", "target_session")); self.setups[key] = record; return record
    def upsert_signal(self, record):
        key = tuple(record[k] for k in ("strategy_code", "strategy_version", "config_hash", "symbol", "setup_date", "scan_slot", "signal_time")); self.signals[key] = record; return record


def inputs():
    daily = {"symbol": "SSI", "timeframe": "1d", "time": "2026-07-01T07:00:00Z", "close_above_high_20": True, "volume_ratio": 1.3}
    base = {"symbol": "SSI", "time": "2026-07-02T02:30:00Z", "close_above_vwap": True, "rsi14": 55, "closed": True}
    return daily, {tf: [{**base, "timeframe": tf}] for tf in ("15m", "60m")}


def test_unapproved_rejected_and_reruns_idempotent():
    strategy, repo = get_strategy("BREAKOUT_V1"), Repo()
    daily, intraday = inputs()
    setup, _ = create_daily_setup(repo, strategy, daily, "2026-07-01", "2026-07-02")
    create_daily_setup(repo, strategy, daily, "2026-07-01", "2026-07-02")
    assert len(repo.setups) == 1
    with pytest.raises(PermissionError):
        scan_candidate(repo, strategy, setup, intraday, "09:30", "2026-07-02T02:30:00Z")
    repo.status = "approved"
    scan_candidate(repo, strategy, setup, intraday, "09:30", "2026-07-02T02:30:00Z")
    scan_candidate(repo, strategy, setup, intraday, "09:30", "2026-07-02T02:30:00Z")
    assert len(repo.signals) == 1
