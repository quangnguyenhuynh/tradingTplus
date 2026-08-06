"""Confirm candidates using the same evaluator used by replay."""

from __future__ import annotations

from datetime import datetime

from .writer import write_live_signal


def _parse(value) -> datetime:
    text = str(value).replace("Z", "+00:00")
    result = datetime.fromisoformat(text)
    if result.tzinfo is None:
        raise ValueError("feature and decision timestamps must be timezone-aware")
    return result


def evaluate_confirmation(strategy, setup: dict, features_by_timeframe: dict, scan_slot: str, decision_time: str):
    required = strategy.required_timeframes(scan_slot)
    selected = {}
    cutoff = _parse(decision_time)
    for timeframe in required:
        candidates = features_by_timeframe.get(timeframe, [])
        eligible = [row for row in candidates if row.get("timeframe") == timeframe and _parse(row["time"]) <= cutoff and row.get("closed", True)]
        if eligible:
            selected[timeframe] = max(eligible, key=lambda row: _parse(row["time"]))
    return strategy.intraday_confirm(setup, selected, scan_slot)


def scan_candidate(repository, strategy, setup: dict, features_by_timeframe: dict, scan_slot: str, decision_time: str, *, live: bool = True):
    target_session = setup.get("target_session")
    if live and repository.signal_exists(strategy.strategy_code, strategy.version,
                                         strategy.config_hash, setup["symbol"], target_session):
        from src.strategies.base import decision
        return None, decision(passed=False, status="already_matched_this_session",
                              reasons=["already_matched_this_session"], metrics={})
    result = evaluate_confirmation(strategy, setup, features_by_timeframe, scan_slot, decision_time)
    if not result.passed:
        return None, result
    record = {
        "strategy_code": strategy.strategy_code, "strategy_version": strategy.version,
        "config_hash": strategy.config_hash, "symbol": setup["symbol"],
        "setup_date": setup["setup_date"], "scan_slot": scan_slot,
        "signal_session": target_session,
        "signal_time": decision_time, "decision": result.to_dict(),
    }
    return (write_live_signal(repository, strategy, record) if live else record), result
