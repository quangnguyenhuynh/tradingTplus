"""Separate, explicitly scoped Analog snapshot/outcome and EOD pipeline."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence

from .core import build_dimensions, resolve_outcomes
from .profile import AnalogProfile


def build_history(
    profile: AnalogProfile,
    feature_rows: Sequence[Mapping[str, Any]],
    sessions: Sequence[date],
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
    selected = sorted(
        (
            row
            for row in feature_rows
            if row.get("timeframe") == "1d"
            and row.get("symbol") in normalized_symbols
            and start <= row["trading_session"] <= end
        ),
        key=lambda row: (row["symbol"], row["trading_session"]),
    )
    by_symbol: dict[str, list[Mapping[str, Any]]] = {}
    for row in sorted(
        (r for r in feature_rows if r.get("timeframe") == "1d"),
        key=lambda r: (r["symbol"], r["trading_session"]),
    ):
        by_symbol.setdefault(row["symbol"], []).append(row)
    snapshots = []
    outcomes: list[dict[str, Any]] = []
    for row in selected:
        history = by_symbol[row["symbol"]]
        position = history.index(row)
        computed = build_dimensions(
            row,
            [prior.get("close") for prior in history[max(0, position - 5) : position]],
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
                    float(row["close"]),
                    sessions,
                    {
                        session: closes.get((row["symbol"], session))
                        for session in sessions
                    },
                    cutoff=max(sessions) if sessions else None,
                )
            )
    deleted = 0
    if apply and repository is not None:
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
        # Production adapter resolves snapshot_key to persisted ids before outcome upsert.
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
    if profile_row.get("configuration", {}).get("distance_threshold") is None:
        reasons.append("DISTANCE_THRESHOLD_NULL")
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
