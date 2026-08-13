"""Production EOD/1d adapters and orchestration for Historical Analog V1."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from typing import Any, Sequence
from zoneinfo import ZoneInfo

import pandas as pd

from src.database.client import SupabaseClient
from src.utils.time_utils import app_now_iso

from .core import fingerprint, match_snapshot
from .pipeline import build_history
from .profile import AnalogProfile, load_source_profile
from .repository import AnalogRepository
from .service import register_profile

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
FEATURE_FIELDS = "symbol,timeframe,time,open,high,low,close,ema20,ema50,rsi14,macd_histogram,high_20_bars,volume_ratio,value_ratio"


def feature_trading_session(value: Any) -> date:
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise ValueError("features.time must be a valid timezone-aware timestamp")
    return stamp.tz_convert(VN_TZ).date()


def _paged(query_factory, page_size: int = 1000) -> list[dict[str, Any]]:
    rows, offset = [], 0
    while True:
        page = query_factory().range(offset, offset + page_size - 1).execute().data or []
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += len(page)


def _daily_through_horizon(
    client: Any,
    symbol: str,
    warm_start: date,
    end: date,
    future_sessions: int,
    *,
    page_size: int = 1000,
    max_pages: int = 100,
) -> list[dict[str, Any]]:
    """Read observed rows until H future sessions are present, without calendar guesses."""
    rows: list[dict[str, Any]] = []
    for page_number in range(max_pages):
        offset = page_number * page_size
        page = (
            client.table("stock_daily")
            .select("symbol,trading_date,close_price")
            .eq("symbol", symbol)
            .gte("trading_date", warm_start.isoformat())
            .order("trading_date")
            .range(offset, offset + page_size - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        observed_future = len(
            {
                date.fromisoformat(row["trading_date"])
                for row in rows
                if date.fromisoformat(row["trading_date"]) > end
            }
        )
        if observed_future >= future_sessions or len(page) < page_size:
            return rows
    raise RuntimeError(
        f"STOCK_DAILY_READ_BOUND_EXCEEDED:{symbol}:max_pages={max_pages}"
    )


def read_inputs(client: Any, symbols: Sequence[str], start: date, end: date, *, history_years: int = 5, future_sessions: int = 5) -> tuple[list[dict[str, Any]], dict[str, list[date]], dict[tuple[str, date], Any]]:
    """Read only canonical 1d features and stock_daily, with paginated warm-up."""
    warm_start = start.replace(year=start.year - history_years) - timedelta(days=14)
    features: list[dict[str, Any]] = []
    sessions: dict[str, list[date]] = {}
    closes: dict[tuple[str, date], Any] = {}
    for symbol in symbols:
        feature_rows = _paged(lambda symbol=symbol: client.table("features").select(FEATURE_FIELDS).eq("symbol", symbol).eq("timeframe", "1d").gte("time", f"{warm_start.isoformat()}T00:00:00+07:00").lte("time", f"{end.isoformat()}T23:59:59.999999+07:00").order("time"))
        for row in feature_rows:
            mapped = dict(row)
            mapped["trading_session"] = feature_trading_session(row.get("time"))
            features.append(mapped)
        daily_rows = _daily_through_horizon(
            client, symbol, warm_start, end, future_sessions
        )
        symbol_sessions = []
        for row in daily_rows:
            session = date.fromisoformat(row["trading_date"])
            symbol_sessions.append(session)
            closes[(symbol, session)] = row.get("close_price")
        sessions[symbol] = sorted(set(symbol_sessions))
    return features, sessions, closes


def exact_profile(repository: AnalogRepository, code: str, version: int, requested_hash: str | None = None) -> tuple[AnalogProfile, dict[str, Any]]:
    source = load_source_profile(code, version, requested_hash)
    row = repository.get_profile(code, version)
    if not row:
        raise ValueError("EXACT_PROFILE_NOT_REGISTERED")
    if row.get("config_hash") != source.config_hash or row.get("configuration") != source.config:
        raise ValueError("CONFIG_HASH_MISMATCH")
    config = deepcopy(source.config)
    config["status"] = row.get("status", config["status"])
    return AnalogProfile(config, source.config_hash), row


def history_build(repository: AnalogRepository, profile: AnalogProfile, *, symbols: Sequence[str], start: date, end: date, mode: str, apply: bool, confirm_replace: bool) -> dict[str, Any]:
    normalized = sorted({str(s).strip().upper() for s in symbols if str(s).strip()})
    features, sessions, closes = read_inputs(
        repository.client,
        normalized,
        start,
        end,
        future_sessions=max(profile.config["horizons"]),
    )
    return build_history(profile, features, sessions, closes, symbols=normalized, start=start, end=end, mode=mode, apply=apply, confirm_replace=confirm_replace, repository=repository)


def hydrate_evidence(repository: AnalogRepository, profile: AnalogProfile, symbol: str, session: date) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    rows = repository.fetch_snapshots(code=profile.code, version=profile.version, config_hash=profile.config_hash, symbol=symbol, through=session)
    outcomes = repository.fetch_outcomes([row["id"] for row in rows])
    grouped: dict[str, dict[int, Any]] = {}
    for outcome in outcomes:
        item = dict(outcome)
        for key in ("target_session", "reference_session"):
            if item.get(key) and not isinstance(item[key], date):
                item[key] = date.fromisoformat(item[key])
        grouped.setdefault(item["snapshot_id"], {})[int(item["horizon_sessions"])] = item
    hydrated = []
    for source in rows:
        row = dict(source)
        row["trading_session"] = date.fromisoformat(row["trading_session"]) if not isinstance(row["trading_session"], date) else row["trading_session"]
        row["status"] = row.pop("evaluation_status")
        row["outcomes"] = grouped.get(row["id"], {})
        hydrated.append(row)
    current = next((row for row in hydrated if row["trading_session"] == session), None)
    return current, [row for row in hydrated if row["trading_session"] < session]


def query_persisted(repository: AnalogRepository, profile: AnalogProfile, *, symbol: str, session: date, apply: bool = False) -> dict[str, Any]:
    reasons = []
    if profile.config["status"] != "approved": reasons.append("EXACT_PROFILE_NOT_APPROVED")
    if profile.config["distance_threshold"] is None: reasons.append("DISTANCE_THRESHOLD_NULL")
    if reasons:
        return {"status": "blocked", "reason_codes": reasons, "persisted": False}
    current, candidates = hydrate_evidence(repository, profile, symbol, session)
    if not current:
        return {"status": "not_evaluable", "reason_codes": ["CURRENT_SNAPSHOT_NOT_FOUND"], "persisted": False}
    result = match_snapshot(current, candidates, profile, query_cutoff=session)
    result["current_snapshot"] = {"id": current["id"], "symbol": symbol, "trading_session": session, "checkpoint": "EOD", "timeframe": "1d", "profile_code": profile.code, "version": profile.version, "config_hash": profile.config_hash}
    result["persisted"] = False
    if apply and result["status"] in {"completed", "insufficient_sample", "not_evaluable"}:
        qfp = fingerprint({"snapshot": current["input_fingerprint"], "profile": profile.config_hash, "session": session, "result": result})
        query = {"snapshot_id": current["id"], "profile_code": profile.code, "version": profile.version, "config_hash": profile.config_hash, "symbol": symbol, "timeframe": "1d", "checkpoint": "EOD", "as_of_session": session, "status": result["status"], "candidate_count": result.get("candidate_count", 0), "usable_sample": result.get("usable_sample", 0), "normalization_parameters": result.get("normalization"), "result_statistics": result.get("statistics"), "baseline_statistics": {h: s.get("baseline_probability") for h, s in result.get("statistics", {}).items()}, "input_fingerprint": current["input_fingerprint"], "query_fingerprint": qfp, "engine_version": f"historical-analog-eod-v{profile.version}", "executed_at": app_now_iso()}
        matches = [{"rank": m["rank"], "matched_snapshot_id": m["snapshot_id"], "distance": m["distance"], "similarity": m["similarity"], "normalized_differences": m["normalized_differences"]} for m in result.get("matches", [])]
        result["audit"] = repository.persist_query(query, matches)
        result["persisted"] = True
    return result


def inspect(repository: AnalogRepository, profile: AnalogProfile, *, symbol: str, session: date, threshold: float) -> dict[str, Any]:
    if threshold < 0:
        raise ValueError("--distance-threshold must be non-negative")
    start = session.replace(year=session.year - int(profile.config["maximum_lookback_years"]))
    features, sessions, closes = read_inputs(
        repository.client,
        [symbol],
        start,
        session,
        future_sessions=max(profile.config["horizons"]),
    )
    built = build_history(profile, features, sessions, closes, symbols=[symbol], start=start, end=session, mode="full", apply=False)
    snapshots = built["snapshots"]
    outcome_by_key: dict[tuple[str, str, date], dict[int, Any]] = {}
    for outcome in built["outcomes"]:
        outcome_by_key.setdefault(outcome["snapshot_key"], {})[outcome["horizon_sessions"]] = outcome
    hydrated = []
    for index, snapshot in enumerate(snapshots):
        row = dict(snapshot)
        row["id"] = f"memory-{index}"
        row["outcomes"] = outcome_by_key.get((profile.config_hash, symbol, row["trading_session"]), {})
        hydrated.append(row)
    current = next((row for row in hydrated if row["trading_session"] == session), None)
    if not current:
        return {"status": "not_evaluable", "reason_codes": ["CURRENT_FEATURE_NOT_FOUND"], "persisted": False, "production": False}
    research_config = deepcopy(profile.config)
    research_config["distance_threshold"] = threshold
    research = AnalogProfile(research_config, profile.config_hash)
    result = match_snapshot(current, [r for r in hydrated if r["trading_session"] < session], research, production=False, query_cutoff=session)
    result.update(current_snapshot={"symbol": symbol, "trading_session": session, "dimensions": current["dimensions"], "evaluation_status": current["status"], "invalid_reason_codes": current["invalid_reasons"]}, persisted=False, production=False, research_threshold=threshold, disclaimer="Non-production research/debug output; not persisted and not approval evidence or investment advice")
    return result


def repository_from_environment() -> AnalogRepository:
    return AnalogRepository(SupabaseClient().get())
