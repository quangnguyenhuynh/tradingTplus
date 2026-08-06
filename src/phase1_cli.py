"""Operational Phase 1 CLI runners. Commands remain explicit and dry-run by default."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from src.backtest.approval import review_strategy
from src.backtest.replay import persist_replay, replay_strategy
from src.database.client import SupabaseClient
from src.database.phase1 import Phase1Repository
from src.pipeline.symbol_scope import normalize_symbol_scope
from src.signals.daily_setup import evaluate_daily_setup
from src.signals.scanner import scan_candidate

VN = ZoneInfo("Asia/Ho_Chi_Minh")


def user_date(value: str) -> str:
    try: return datetime.strptime(value, "%d/%m/%Y").date().isoformat()
    except ValueError as exc: raise ValueError(f"invalid date {value!r}; expected DD/MM/YYYY") from exc


def repository(): return Phase1Repository(SupabaseClient())


def _market_date(value) -> str:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None: raise ValueError("Phase 1 feature/candle timestamps must be timezone-aware")
    return parsed.astimezone(VN).date().isoformat()


def _register(repo, strategy):
    return repo.upsert_strategy({"strategy_code": strategy.strategy_code, "version": strategy.version,
        "config_hash": strategy.config_hash, "config": dict(strategy.config), "status": "draft"})


def run_daily_setup(strategy, date, target_session, symbols, *, write=False, repo=None):
    repo, setup_date, target = repo or repository(), user_date(date), user_date(target_session)
    scope = normalize_symbol_scope(symbols)
    rows = repo.features(scope, ["1d"], f"{setup_date}T00:00:00+07:00", f"{setup_date}T23:59:59+07:00")
    latest = {r["symbol"]: r for r in rows}
    results = []
    if write and repo.strategy_status(strategy.strategy_code, strategy.version, strategy.config_hash) != "approved": raise PermissionError("exact strategy version/config is not approved")
    for symbol in scope:
        feature = latest.get(symbol, {"symbol": symbol, "timeframe": "1d", "time": setup_date})
        record, decision = evaluate_daily_setup(strategy, feature, setup_date, target)
        if write: record = repo.upsert_setup(record)
        results.append({"symbol": symbol, "status": decision.status, "record": record})
    return {"status": "OK", "dry_run": not write, "setup_date": setup_date, "target_session": target, "symbols": scope, "results": results}


def run_scan(strategy, date, slot, symbols, *, write=False, repo=None):
    repo, session, scope = repo or repository(), user_date(date), normalize_symbol_scope(symbols)
    decision = datetime.combine(datetime.fromisoformat(session).date(), time.fromisoformat(slot), VN).isoformat()
    setups = repo.passed_setups(session, strategy.strategy_code, strategy.version, strategy.config_hash, scope)
    start, end = f"{session}T00:00:00+07:00", decision
    features = repo.features(scope, ["15m", "60m"], start, end)
    grouped = {(s, tf): [] for s in scope for tf in ("15m", "60m")}
    for row in features: grouped.setdefault((row["symbol"], row["timeframe"]), []).append(row)
    if write and repo.strategy_status(strategy.strategy_code, strategy.version, strategy.config_hash) != "approved": raise PermissionError("exact strategy version/config is not approved")
    output = []
    for setup in setups:
        by_tf = {tf: grouped.get((setup["symbol"], tf), []) for tf in strategy.required_timeframes(slot)}
        record, result = scan_candidate(repo, strategy, setup, by_tf, slot, decision, live=write)
        output.append({"symbol": setup["symbol"], "status": result.status, "record": record})
    return {"status": "OK", "dry_run": not write, "signal_session": session, "slot": slot, "symbols": scope, "results": output}


def run_approve(strategy, run_id, decision, owner, notes, *, repo=None):
    return review_strategy(repo or repository(), strategy, run_id, decision, owner, notes)


def _artifacts(directory, summary, signals):
    path = Path(directory); path.mkdir(parents=True, exist_ok=True)
    (path / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")
    keys = sorted({k for row in signals for k in row})
    with (path / "signals.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys); writer.writeheader()
        for row in signals: writer.writerow({k: json.dumps(row[k], sort_keys=True) if isinstance(row.get(k), (dict,list)) else row.get(k) for k in keys})
    (path / "review.md").write_text("# Phase 1 backtest review\n\n```json\n" + json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n```\n")


def run_backtest(strategy, from_date, to_date, symbols, *, write=False, repo=None, output_dir=None, commission=0.0, sell_tax=0.0, slippage=0.0):
    repo, start, end, scope = repo or repository(), user_date(from_date), user_date(to_date), normalize_symbol_scope(symbols)
    # Load the observed axis beyond the requested end; a bounded tail supplies H+5.
    daily = repo.daily(scope, start, "9999-12-31")
    observed = sorted({r["trading_date"] for r in daily})
    scoped_axis = [d for d in observed if d >= start]
    setup_axis = [d for d in scoped_axis if d <= end]
    last_entry = scoped_axis[len(setup_axis)] if len(scoped_axis) > len(setup_axis) else end
    features = repo.features(scope, ["1d", "15m", "60m"], f"{start}T00:00:00+07:00", f"{last_entry}T23:59:59+07:00")
    candles = repo.intraday(scope, f"{start}T00:00:00+07:00", f"{last_entry}T23:59:59+07:00")
    # Data assembly is deliberately per-symbol and session; absent rows remain absent.
    signals = []
    for symbol in scope:
        sessions=[]
        # Include one observed entry session after --to while restricting setup D
        # to the requested inclusive range.
        symbol_axis = scoped_axis[:len(setup_axis) + 1]
        for day in symbol_axis:
            one = [r for r in features if r["symbol"] == symbol and r["timeframe"] == "1d" and _market_date(r["time"]) == day]
            daily_feature = one[-1] if one else {"symbol":symbol,"timeframe":"1d","time":f"{day}T00:00:00+07:00"}
            day_intraday = [r for r in features if r["symbol"] == symbol and r["timeframe"] in ("15m","60m") and _market_date(r["time"]) == day]
            scans = {}
            for slot in ("09:30","11:30","13:30","14:30"):
                cutoff=datetime.combine(datetime.fromisoformat(day).date(),time.fromisoformat(slot),VN).isoformat()
                scans[slot]={"decision_time":cutoff,"features":{tf:[r for r in day_intraday if r["timeframe"]==tf] for tf in ("15m","60m")}}
            sessions.append({"session": day, "daily_feature": daily_feature, "scans": scans,
                "candles_1m": [r for r in candles if r["symbol"]==symbol and _market_date(r["time"])==day],
                "daily_outcomes": [r for r in daily if r["symbol"] == symbol]})
        signals.extend(replay_strategy(strategy, sessions, cost_rate=commission+sell_tax+slippage)["signals"])
    replay = {"mode":"daily_intraday", "signals":signals, "metrics": __import__('src.backtest.metrics', fromlist=['calculate_metrics']).calculate_metrics(signals, commission+sell_tax+slippage), "status":"completed"}
    assumptions={"calendar_source":"observed_stock_daily_v1","evaluator_version":"phase1_v1","entry_model":"next_1m_open_v1","exit_model":"observed_session_close_v1","commission":commission,"sell_tax":sell_tax,"slippage":slippage}
    identity={"strategy_code":strategy.strategy_code,"strategy_version":strategy.version,"config_hash":strategy.config_hash,"scope":{"from":start,"to":end,"symbols":scope},"mode":"daily_intraday","assumptions":assumptions}
    key=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    run={**identity,"idempotency_key":key,"data_quality":{"observed_session_count":len(observed),"signal_count":len(signals)}}
    persisted = persist_replay(repo, run, replay) if write else {**run,"status":"completed","metrics":replay["metrics"]}
    summary={"status":"completed","dry_run":not write,"run":persisted,"metrics":replay["metrics"],"signal_count":len(signals)}
    if output_dir: _artifacts(output_dir, summary, signals)
    return summary
