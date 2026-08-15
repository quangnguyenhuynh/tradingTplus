"""Chronological calibration and walk-forward evidence generation."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Any, Mapping, Sequence

from .core import match_snapshot
from .profile import AnalogProfile


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
    if (
        run_type == "calibration"
        and final_test_start is not None
        and end >= final_test_start
    ):
        raise ValueError(
            "calibration interval must end before the untouched final-test interval"
        )
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
    for horizon in profile.config["horizons"]:
        by_horizon[horizon]
    total_queries = insufficient = 0
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
        for horizon in profile.config["horizons"]:
            actual = current.get("outcomes", {}).get(horizon)
            if not actual or actual.get("status") != "completed":
                status = actual.get("status", "missing") if actual else "missing"
                reason = (
                    actual.get("reason") or actual.get("unavailable_reason")
                    if actual
                    else None
                )
                reasons[f"CURRENT_OUTCOME_{status.upper()}_H{horizon}"] += 1
                if reason:
                    reasons[f"CURRENT_OUTCOME_H{horizon}:{reason}"] += 1
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
    return {
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


def calibrate(
    profile: AnalogProfile,
    snapshots: Sequence[Mapping[str, Any]],
    thresholds: Sequence[float],
    *,
    training_start: date,
    training_end: date,
    final_test_start: date,
) -> dict[str, Any]:
    if training_end >= final_test_start:
        raise ValueError("training/calibration must not touch the final-test interval")
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
    return {
        "status": "completed",
        "run_type": "calibration",
        "profile_config_hash": profile.config_hash,
        "mutated_profile": False,
        "qualifies_for_approval": False,
        "candidates": artifacts,
    }
