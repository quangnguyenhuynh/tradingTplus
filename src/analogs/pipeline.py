"""Separate, explicitly scoped Analog snapshot/outcome and EOD pipeline."""

from __future__ import annotations

from datetime import date
import math
from typing import Any, Mapping, Sequence

from .core import build_dimensions, resolve_outcomes
from .profile import AnalogProfile


def build_history(
    profile: AnalogProfile,
    feature_rows: Sequence[Mapping[str, Any]],
    sessions: Sequence[date] | Mapping[str, Sequence[date]],
    closes: Mapping[tuple[str, date], float],
    *,
    symbols: Sequence[str],
    start: date,
    end: date,
    mode: str,
    apply: bool = False,
    confirm_replace: bool = False,
    repository: Any | None = None,
) -> dict[str, Any]:
    if mode not in {"full", "incremental", "replace"}:
        raise ValueError("mode must be full, incremental, or replace")
    normalized_symbols = sorted(
        {symbol.upper() for symbol in symbols if symbol.strip()}
    )
    if not normalized_symbols:
        raise ValueError("an explicit symbol scope is required")
    if start > end:
        raise ValueError("start must not be after end")
    if mode == "replace" and apply and not confirm_replace:
        raise ValueError("scoped replace requires --confirm-replace")
    refresh_sessions: dict[str, set[date]] = {}
    if mode == "incremental":
        for symbol in normalized_symbols:
            observed = (
                list(sessions.get(symbol, ()))
                if isinstance(sessions, Mapping)
                else list(sessions)
            )
            before = [session for session in observed if session < start]
            refresh_sessions[symbol] = set(before[-max(profile.config["horizons"]) :])
    selected = sorted(
        (
            row
            for row in feature_rows
            if row.get("timeframe") == "1d"
            and row.get("symbol") in normalized_symbols
            and (
                start <= row["trading_session"] <= end
                or row["trading_session"]
                in refresh_sessions.get(row.get("symbol"), set())
            )
        ),
        key=lambda row: (row["symbol"], row["trading_session"]),
    )
    snapshots = []
    outcomes: list[dict[str, Any]] = []
    for row in selected:
        symbol_sessions = (
            sessions.get(row["symbol"], ())
            if isinstance(sessions, Mapping)
            else sessions
        )
        session_position = (
            list(symbol_sessions).index(row["trading_session"])
            if row["trading_session"] in symbol_sessions
            else -1
        )
        prior_closes = (
            [
                closes.get((row["symbol"], prior))
                for prior in symbol_sessions[
                    max(0, session_position - 5) : session_position
                ]
            ]
            if session_position >= 0
            else []
        )
        computed = build_dimensions(
            row,
            prior_closes,
        )
        snapshot = {
            "profile_code": profile.code,
            "version": profile.version,
            "config_hash": profile.config_hash,
            "symbol": row["symbol"],
            "timeframe": "1d",
            "checkpoint": "EOD",
            "trading_session": row["trading_session"],
            **computed,
        }
        snapshots.append(snapshot)
        if computed["status"] == "evaluable":
            reference = closes.get((row["symbol"], row["trading_session"]))
            try:
                reference_close = float(reference)
            except (TypeError, ValueError):
                reference_close = math.nan
            if not math.isfinite(reference_close) or reference_close <= 0:
                outcomes.extend(
                    {
                        "snapshot_key": (
                            profile.config_hash,
                            row["symbol"],
                            row["trading_session"],
                        ),
                        "horizon_sessions": horizon,
                        "reference_session": row["trading_session"],
                        "status": "unavailable",
                        "reason": "REFERENCE_CLOSE_MISSING_OR_INVALID",
                    }
                    for horizon in profile.config["horizons"]
                )
                continue
            outcomes.extend(
                {
                    "snapshot_key": (
                        profile.config_hash,
                        row["symbol"],
                        row["trading_session"],
                    ),
                    **outcome,
                }
                for outcome in resolve_outcomes(
                    row["trading_session"],
                    reference_close,
                    symbol_sessions,
                    {
                        session: closes.get((row["symbol"], session))
                        for session in symbol_sessions
                    },
                    cutoff=max(symbol_sessions) if symbol_sessions else None,
                    horizons=profile.config["horizons"],
                )
            )
    deleted = 0
    if apply and repository is not None:
        persistence_start = min(
            (row["trading_session"] for row in snapshots), default=start
        )
        if mode == "replace":
            deleted = repository.replace_scope(
                code=profile.code,
                version=profile.version,
                config_hash=profile.config_hash,
                symbols=normalized_symbols,
                start=start.isoformat(),
                end=end.isoformat(),
            )
        repository.upsert_snapshots(snapshots)
        if not hasattr(repository, "resolve_snapshot_ids"):
            persisted = []  # Compatibility for dry/unit repositories.
        else:
            persisted = repository.resolve_snapshot_ids(
                code=profile.code,
                version=profile.version,
                config_hash=profile.config_hash,
                symbols=normalized_symbols,
                start=persistence_start.isoformat(),
                end=end.isoformat(),
            )
        ids = {
            (row["config_hash"], row["symbol"], _as_date(row["trading_session"])): row[
                "id"
            ]
            for row in persisted
        }
        persisted_outcomes = []
        for outcome in outcomes:
            key = outcome["snapshot_key"]
            snapshot_id = ids.get(key)
            if not snapshot_id and persisted:
                raise RuntimeError(f"persisted snapshot id not found for {key}")
            if not snapshot_id:
                continue
            mapped = {k: v for k, v in outcome.items() if k != "snapshot_key"}
            mapped["snapshot_id"] = snapshot_id
            persisted_outcomes.append(mapped)
        if hasattr(repository, "upsert_outcomes"):
            repository.upsert_outcomes(persisted_outcomes)
    return {
        "status": "completed",
        "profile_code": profile.code,
        "version": profile.version,
        "config_hash": profile.config_hash,
        "mode": mode,
        "range": [start.isoformat(), end.isoformat()],
        "symbols": normalized_symbols,
        "dry_run": not apply,
        "snapshot_count": len(snapshots),
        "outcome_count": len(outcomes),
        "deleted_count": deleted,
        "reason_counts": {
            reason: sum(reason in row["invalid_reasons"] for row in snapshots)
            for reason in sorted(
                {reason for row in snapshots for reason in row["invalid_reasons"]}
            )
        },
        "snapshots": snapshots,
        "outcomes": outcomes,
    }


def _as_date(value: Any) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def daily_run(
    profile_row: Mapping[str, Any],
    *,
    symbols: Sequence[str],
    session: date,
    apply: bool = False,
) -> dict[str, Any]:
    if not symbols:
        raise ValueError("daily Analog run requires explicit symbols")
    reasons = []
    if profile_row.get("status") != "approved":
        reasons.append("EXACT_PROFILE_NOT_APPROVED")
    return {
        "status": "blocked" if reasons else ("ready" if apply else "dry_run"),
        "profile_code": profile_row.get("profile_code"),
        "version": profile_row.get("version"),
        "config_hash": profile_row.get("config_hash"),
        "session": session.isoformat(),
        "symbols": sorted({s.upper() for s in symbols}),
        "dry_run": not apply,
        "reason_codes": reasons,
        "order": [
            "verify_1d_features",
            "create_snapshots",
            "update_outcomes",
            "persist_approved_queries",
        ],
    }
