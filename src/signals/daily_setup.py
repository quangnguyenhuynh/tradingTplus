"""Create watchlist candidates from canonical 1d feature rows."""

from __future__ import annotations

from .writer import write_setup


def evaluate_daily_setup(strategy, feature: dict, setup_date: str, target_session: str) -> tuple[dict, object]:
    decision = strategy.daily_setup(feature)
    record = {
        "strategy_code": strategy.strategy_code, "strategy_version": strategy.version,
        "config_hash": strategy.config_hash, "symbol": feature.get("symbol"),
        "setup_date": setup_date, "target_session": target_session,
        "status": decision.status, "decision": decision.to_dict(),
    }
    return record, decision


def create_daily_setup(repository, strategy, feature: dict, setup_date: str, target_session: str):
    record, result = evaluate_daily_setup(strategy, feature, setup_date, target_session)
    return (write_setup(repository, record) if result.passed else record), result
