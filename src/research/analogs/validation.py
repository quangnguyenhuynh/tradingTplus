"""Chronological calibration and walk-forward evidence generation."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .core import fingerprint, match_snapshot
from .profile import AnalogProfile

# STRICT calibration label-boundary policy marker. Non-calibration walk-forward
# output remains byte-compatible with the pre-STRICT contract; only run_type
# "calibration" carries these fields.
CALIBRATION_POLICY_MARKER = "STRICT"
CALIBRATION_POLICY_VERSION = "1"

# Runtime-safe code identity: these source modules define the calibration
# method and scoring contract. The hash changes whenever their bytes change,
# so before/after evidence is distinguishable without fabricating a git revision.
_IDENTITY_MODULES = ("core.py", "profile.py", "validation.py")


def _calibration_code_identity() -> str:
    digest = hashlib.sha256()
    for name in _IDENTITY_MODULES:
        digest.update(name.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def _coerce_session(value: Any) -> date | None:
    """Parse a label ``target_session`` into a date; None when missing/invalid.

    Accepts ``date``, ``datetime``, and ISO date/datetime strings. Anything else
    (``None``, ``bool``, ``int``, ``float``, empty or unparseable strings) is
    invalid and is never scored as a calibration label.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(text).date()
        except ValueError:
            return None
    return None


def _snapshot_data_identity(row: Mapping[str, Any]) -> dict[str, Any]:
    """Semantic, rebuild-stable subset of a snapshot that drives the evidence.

    Includes the eligibility-deciding fields (``symbol``, ``profile_code``,
    ``version``, ``config_hash``, ``timeframe``, ``checkpoint``, ``status``,
    ``trading_session``, ``outcomes``) plus ``dimensions``, so a change that
    alters which candidates are eligible or how they are scored always changes
    the identity. Persistence-only metadata (``id``) and derived lineage fields
    are excluded, so identical market data still produces an identical identity.
    """
    return {
        "symbol": row.get("symbol"),
        "profile_code": row.get("profile_code"),
        "version": row.get("version"),
        "config_hash": row.get("config_hash"),
        "timeframe": row.get("timeframe"),
        "checkpoint": row.get("checkpoint"),
        "trading_session": row.get("trading_session"),
        "status": row.get("status"),
        "dimensions": row.get("dimensions"),
        "outcomes": row.get("outcomes"),
    }


def calibration_identity(
    profile: AnalogProfile,
    snapshots: Sequence[Mapping[str, Any]],
    *,
    start: date,
    end: date,
    final_test_start: date,
) -> dict[str, Any]:
    """Deterministic STRICT identity for one calibration evidence run."""
    ordered = sorted(snapshots, key=lambda row: (row["trading_session"], row["symbol"]))
    identity: dict[str, Any] = {
        "policy": {
            "marker": CALIBRATION_POLICY_MARKER,
            "version": CALIBRATION_POLICY_VERSION,
        },
        "boundaries": {
            "training_start": start.isoformat(),
            "training_end": end.isoformat(),
            "final_test_start": final_test_start.isoformat(),
        },
        "profile_identity": {
            "code": profile.code,
            "version": profile.version,
            "config_hash": profile.config_hash,
        },
        "code_identity": _calibration_code_identity(),
        "data_identity": fingerprint(
            [_snapshot_data_identity(row) for row in ordered]
        ),
    }
    identity["evidence_identity"] = fingerprint(identity)
    return identity


def validate_calibration_boundaries(
    training_start: date,
    training_end: date,
    final_test_start: date,
) -> None:
    """Fail-closed calibration boundary preflight shared by CLI and direct calls."""
    if training_start > training_end:
        raise ValueError("calibration start must not be after its end")
    if training_end >= final_test_start:
        raise ValueError(
            "calibration interval must end before the untouched final-test interval"
        )


def profile_with_threshold(profile: AnalogProfile, threshold: float) -> AnalogProfile:
    """Backward-compatible helper; thresholds no longer mutate top-k semantics."""
    if float(threshold) < 0:
        raise ValueError("distance threshold must be non-negative")
    return profile


def _brier(probabilities: list[float], actuals: list[int]) -> float | None:
    return (
        sum((p - y) ** 2 for p, y in zip(probabilities, actuals)) / len(probabilities)
        if probabilities
        else None
    )


def walk_forward(
    profile: AnalogProfile,
    snapshots: Sequence[Mapping[str, Any]],
    *,
    start: date,
    end: date,
    final_test_start: date | None = None,
    run_type: str = "validation",
) -> dict[str, Any]:
    is_calibration = run_type == "calibration"
    if is_calibration:
        if final_test_start is None:
            raise ValueError("calibration requires a final-test start boundary")
        validate_calibration_boundaries(start, end, final_test_start)
    ordered = sorted(snapshots, key=lambda row: (row["trading_session"], row["symbol"]))
    metrics: dict[int, dict[str, Any]] = {}
    reasons: Counter[str] = Counter()
    by_horizon: defaultdict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "p": [],
            "y": [],
            "base": [],
            "median_error": [],
            "years": defaultdict(int),
        }
    )
    label_accounting: defaultdict[int, dict[str, int]] = defaultdict(
        lambda: {
            "scored": 0,
            "censored": 0,
            "pending": 0,
            "missing": 0,
            "invalid": 0,
            "unavailable": 0,
            "unknown": 0,
        }
    )
    for horizon in profile.config["horizons"]:
        by_horizon[horizon]
    total_queries = insufficient = eligible_forecasts = 0
    for current in ordered:
        session = current["trading_session"]
        if not (start <= session <= end):
            continue
        total_queries += 1
        result = match_snapshot(
            current, ordered, profile, production=False, query_cutoff=session
        )
        if result["status"] != "completed":
            if result["status"] == "insufficient_sample":
                insufficient += 1
            for reason in result.get("reason_codes", [result["status"]]):
                reasons[reason] += 1
            continue
        eligible_forecasts += 1
        for horizon in profile.config["horizons"]:
            actual = current.get("outcomes", {}).get(horizon)
            if not actual:
                reasons[f"CURRENT_OUTCOME_MISSING_H{horizon}"] += 1
                if is_calibration:
                    label_accounting[horizon]["missing"] += 1
                continue
            status = actual.get("status")
            if status != "completed":
                status_key = status.upper() if isinstance(status, str) else "MISSING"
                reasons[f"CURRENT_OUTCOME_{status_key}_H{horizon}"] += 1
                reason = actual.get("reason") or actual.get("unavailable_reason")
                if reason:
                    reasons[f"CURRENT_OUTCOME_H{horizon}:{reason}"] += 1
                if is_calibration:
                    category = {
                        "MISSING": "missing",
                        "PENDING": "pending",
                        "UNAVAILABLE": "unavailable",
                    }.get(status_key, "unknown")
                    label_accounting[horizon][category] += 1
                continue
            if is_calibration:
                target_session = _coerce_session(actual.get("target_session"))
                if target_session is None:
                    reasons[f"CURRENT_OUTCOME_INVALID_TARGET_SESSION_H{horizon}"] += 1
                    label_accounting[horizon]["invalid"] += 1
                    continue
                if target_session > end:
                    reasons[f"CURRENT_OUTCOME_CENSORED_H{horizon}"] += 1
                    label_accounting[horizon]["censored"] += 1
                    continue
            stats = result["statistics"][str(horizon)]
            bucket = by_horizon[horizon]
            bucket["p"].append(stats["positive_probability"])
            bucket["y"].append(int(actual["return_ratio"] > 0))
            bucket["base"].append(stats["baseline_probability"])
            bucket["median_error"].append(
                abs(stats["median_return"] - actual["return_ratio"])
            )
            bucket["years"][session.year] += 1
            if is_calibration:
                label_accounting[horizon]["scored"] += 1
    for horizon, bucket in by_horizon.items():
        calibration = []
        for lower in (0, 0.2, 0.4, 0.6, 0.8):
            indexes = [
                i
                for i, p in enumerate(bucket["p"])
                if lower <= p <= (1 if lower == 0.8 else lower + 0.2)
            ]
            calibration.append(
                {
                    "lower": lower,
                    "upper": min(1.0, lower + 0.2),
                    "count": len(indexes),
                    "mean_forecast": (
                        sum(bucket["p"][i] for i in indexes) / len(indexes)
                        if indexes
                        else None
                    ),
                    "observed_positive": (
                        sum(bucket["y"][i] for i in indexes) / len(indexes)
                        if indexes
                        else None
                    ),
                }
            )
        metrics[horizon] = {
            "forecast_count": len(bucket["p"]),
            "brier_score": _brier(bucket["p"], bucket["y"]),
            "baseline_brier_score": _brier(bucket["base"], bucket["y"]),
            "calibration_buckets": calibration,
            "mean_probability_lift": (
                sum(p - b for p, b in zip(bucket["p"], bucket["base"]))
                / len(bucket["p"])
                if bucket["p"]
                else None
            ),
            "median_return_mae": (
                sum(bucket["median_error"]) / len(bucket["median_error"])
                if bucket["median_error"]
                else None
            ),
            "stability_by_year": dict(bucket["years"]),
        }
    result = {
        "status": "completed",
        "run_type": run_type,
        "range": [start.isoformat(), end.isoformat()],
        "query_count": total_queries,
        "coverage": (
            (total_queries - insufficient) / total_queries if total_queries else 0.0
        ),
        "insufficient_sample_count": insufficient,
        "metrics": metrics,
        "reason_counts": dict(reasons),
    }
    if is_calibration:
        result.update(
            {
                "eligible_forecasts": eligible_forecasts,
                "not_evaluable_queries": total_queries - eligible_forecasts,
                "label_accounting": {
                    horizon: dict(label_accounting[horizon])
                    for horizon in profile.config["horizons"]
                },
            }
        )
        result.update(
            calibration_identity(
                profile,
                snapshots,
                start=start,
                end=end,
                final_test_start=final_test_start,
            )
        )
    return result


def calibrate(
    profile: AnalogProfile,
    snapshots: Sequence[Mapping[str, Any]],
    thresholds: Sequence[float],
    *,
    training_start: date,
    training_end: date,
    final_test_start: date,
) -> dict[str, Any]:
    validate_calibration_boundaries(training_start, training_end, final_test_start)
    if not thresholds:
        raise ValueError("explicit candidate thresholds are required")
    artifacts = []
    for threshold in thresholds:
        candidate = profile_with_threshold(profile, threshold)
        result = walk_forward(
            candidate,
            snapshots,
            start=training_start,
            end=training_end,
            final_test_start=final_test_start,
            run_type="calibration",
        )
        artifacts.append(
            {
                "legacy_threshold_ignored": threshold,
                "candidate_config_hash": candidate.config_hash,
                "evidence": result,
            }
        )
    output = {
        "status": "completed",
        "run_type": "calibration",
        "profile_config_hash": profile.config_hash,
        "mutated_profile": False,
        "qualifies_for_approval": False,
        "candidates": artifacts,
    }
    output.update(
        calibration_identity(
            profile,
            snapshots,
            start=training_start,
            end=training_end,
            final_test_start=final_test_start,
        )
    )
    return output
