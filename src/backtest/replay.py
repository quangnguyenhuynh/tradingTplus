"""Replay daily setup D and intraday confirmation on next observed session E."""

from __future__ import annotations

from src.signals.daily_setup import evaluate_daily_setup
from src.signals.scanner import scan_candidate

from .execution import estimate_entry
from .metrics import calculate_metrics
from .outcome import map_outcomes


def replay_strategy(strategy, sessions: list[dict], *, cost_rate: float = 0.0) -> dict:
    signals = []
    ordered = sorted(sessions, key=lambda item: item["session"])
    for index in range(len(ordered) - 1):
        setup_session, entry_session = ordered[index], ordered[index + 1]
        setup, daily_decision = evaluate_daily_setup(strategy, setup_session["daily_feature"], setup_session["session"], entry_session["session"])
        if not daily_decision.passed:
            continue
        for scan_slot, scan in sorted(entry_session.get("scans", {}).items()):
            signal, intraday_decision = scan_candidate(None, strategy, setup, scan["features"], scan_slot, scan["decision_time"], live=False)
            if not intraday_decision.passed:
                continue
            entry = estimate_entry(entry_session.get("candles_1m", []), scan["decision_time"])
            record = {**signal, **entry, "entry_session": entry_session["session"]}
            record.update(map_outcomes(entry_session.get("daily_outcomes", []), entry_session["session"], entry["entry_price"]))
            signals.append(record)
    return {"mode": "daily_intraday", "signals": signals, "metrics": calculate_metrics(signals, cost_rate), "status": "completed"}


def persist_replay(repository, run_record: dict, replay: dict) -> dict:
    run = repository.upsert_backtest_run({**run_record, "mode": replay["mode"], "status": replay["status"], "metrics": replay["metrics"]})
    for signal in replay["signals"]:
        repository.upsert_backtest_signal({**signal, "backtest_run_id": run["id"]})
    return run
