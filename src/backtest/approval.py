"""Owner review gate for one exact strategy version and config hash."""


def review_strategy(repository, strategy, backtest_run_id: str, decision: str, owner: str, notes: str) -> dict:
    if decision not in {"approve", "reject"}:
        raise ValueError("review decision must be approve or reject")
    if not owner.strip() or not notes.strip():
        raise ValueError("owner and review notes are required")
    run = repository.get_backtest_run(backtest_run_id)
    exact = run and run.get("strategy_code") == strategy.strategy_code and int(run.get("strategy_version")) == strategy.version and run.get("config_hash") == strategy.config_hash
    if not exact or run.get("status") != "completed" or run.get("mode") != "daily_intraday" or not run.get("metrics"):
        raise ValueError("completed two-stage backtest evidence for exact strategy version/config is required")
    review = repository.upsert_strategy_review({"strategy_code": strategy.strategy_code, "strategy_version": strategy.version, "config_hash": strategy.config_hash, "backtest_run_id": backtest_run_id, "decision": decision, "owner": owner, "notes": notes})
    if decision == "approve":
        repository.update_strategy_status(strategy.strategy_code, strategy.version, strategy.config_hash, "approved")
    return review
