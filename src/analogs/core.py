"""Pure snapshot, outcome, and historical-matching algorithms for EOD V1."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from statistics import NormalDist, median
from typing import Any, Iterable, Mapping, Sequence

DIMENSIONS = (
    "return_5d",
    "price_vs_ema20_pct",
    "ema20_vs_ema50_pct",
    "rsi14",
    "macd_histogram_pct",
    "distance_to_high20_pct",
    "volume_ratio",
    "value_ratio",
    "close_position_in_candle",
)


def _number(value: Any, reason: str, reasons: list[str]) -> float | None:
    if value is None or isinstance(value, bool):
        reasons.append(f"MISSING_{reason}")
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        reasons.append(f"INVALID_{reason}")
        return None
    if not math.isfinite(result):
        reasons.append(f"NON_FINITE_{reason}")
        return None
    return result


def _ratio(
    numerator: float | None,
    denominator: float | None,
    reason: str,
    reasons: list[str],
    *,
    minus_one: bool = False,
) -> float | None:
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        reasons.append(f"ZERO_DENOMINATOR_{reason}")
        return None
    result = numerator / denominator - (1 if minus_one else 0)
    if not math.isfinite(result):
        reasons.append(f"NON_FINITE_{reason}")
        return None
    return result


def build_dimensions(
    feature: Mapping[str, Any], preceding_closes: Sequence[Any]
) -> dict[str, Any]:
    """Calculate exact V1 dimensions without mutating the feature layer."""
    reasons: list[str] = []
    close = _number(feature.get("close"), "CLOSE", reasons)
    low = _number(feature.get("low"), "LOW", reasons)
    high = _number(feature.get("high"), "HIGH", reasons)
    ema20 = _number(feature.get("ema20"), "EMA20", reasons)
    ema50 = _number(feature.get("ema50"), "EMA50", reasons)
    macd = _number(feature.get("macd_histogram"), "MACD_HISTOGRAM", reasons)
    high20 = _number(feature.get("high_20_bars"), "HIGH_20", reasons)
    rsi = _number(feature.get("rsi14"), "RSI14", reasons)
    volume_ratio = _number(feature.get("volume_ratio"), "VOLUME_RATIO", reasons)
    value_ratio = _number(feature.get("value_ratio"), "VALUE_RATIO", reasons)
    prior5 = None
    if len(preceding_closes) < 5:
        reasons.append("INSUFFICIENT_FIVE_SESSION_HISTORY")
    else:
        prior5 = _number(preceding_closes[-5], "CLOSE_D_MINUS_5", reasons)
    candle_range = None if high is None or low is None else high - low
    if candle_range == 0:
        reasons.append("ZERO_CANDLE_RANGE")
    values = {
        "return_5d": _ratio(close, prior5, "RETURN_5D", reasons, minus_one=True),
        "price_vs_ema20_pct": _ratio(
            close, ema20, "PRICE_VS_EMA20", reasons, minus_one=True
        ),
        "ema20_vs_ema50_pct": _ratio(
            ema20, ema50, "EMA20_VS_EMA50", reasons, minus_one=True
        ),
        "rsi14": rsi,
        "macd_histogram_pct": _ratio(macd, close, "MACD_HISTOGRAM_PCT", reasons),
        "distance_to_high20_pct": _ratio(
            close, high20, "DISTANCE_TO_HIGH20", reasons, minus_one=True
        ),
        "volume_ratio": volume_ratio,
        "value_ratio": value_ratio,
        "close_position_in_candle": _ratio(
            None if close is None or low is None else close - low,
            candle_range,
            "CLOSE_POSITION",
            reasons,
        ),
    }
    missing = [name for name, value in values.items() if value is None]
    return {
        "status": "evaluable" if not missing and not reasons else "not_evaluable",
        "dimensions": values,
        "invalid_reasons": sorted(set(reasons)),
        "input_fingerprint": fingerprint(
            {"feature": dict(feature), "preceding_closes": list(preceding_closes[-5:])}
        ),
    }


def fingerprint(value: Any) -> str:
    def safe(item: Any) -> Any:
        if isinstance(item, Mapping):
            return {str(key): safe(val) for key, val in item.items()}
        if isinstance(item, (list, tuple)):
            return [safe(val) for val in item]
        if isinstance(item, float) and not math.isfinite(item):
            return {"invalid_float": repr(item)}
        return item

    encoded = json.dumps(
        safe(value), sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def resolve_outcomes(
    snapshot_session: date,
    reference_close: float,
    sessions: Sequence[date],
    closes: Mapping[date, Any],
    horizons: Sequence[int] = (1, 3, 5),
    *,
    cutoff: date | None = None,
    unavailable_sessions: Iterable[date] = (),
) -> list[dict[str, Any]]:
    ordered = sorted(set(sessions))
    unavailable = set(unavailable_sessions)
    if snapshot_session not in ordered:
        raise ValueError(
            "snapshot session is absent from the verified trading calendar"
        )
    position = ordered.index(snapshot_session)
    rows = []
    for horizon in horizons:
        target_position = position + horizon
        if target_position >= len(ordered) or (
            cutoff is not None and ordered[target_position] > cutoff
        ):
            rows.append(
                {
                    "horizon_sessions": horizon,
                    "status": "pending",
                    "reason": "TARGET_SESSION_NOT_YET_OBSERVABLE",
                }
            )
            continue
        target = ordered[target_position]
        value = closes.get(target)
        if target in unavailable or value is None:
            rows.append(
                {
                    "horizon_sessions": horizon,
                    "target_session": target,
                    "status": "unavailable",
                    "reason": "VERIFIED_SESSION_PRICE_MISSING",
                }
            )
            continue
        target_close = float(value)
        if not math.isfinite(target_close) or reference_close <= 0:
            rows.append(
                {
                    "horizon_sessions": horizon,
                    "target_session": target,
                    "status": "unavailable",
                    "reason": "INVALID_CLOSE",
                }
            )
            continue
        rows.append(
            {
                "horizon_sessions": horizon,
                "reference_session": snapshot_session,
                "reference_close": reference_close,
                "target_session": target,
                "target_close": target_close,
                "return_ratio": target_close / reference_close - 1,
                "status": "completed",
                "reason": None,
            }
        )
    return rows


def percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile requires values")
    point = (len(ordered) - 1) * q
    lo = math.floor(point)
    hi = math.ceil(point)
    return (
        ordered[lo]
        if lo == hi
        else ordered[lo] + (ordered[hi] - ordered[lo]) * (point - lo)
    )


def fit_median_iqr(rows: Sequence[Mapping[str, float]]) -> dict[str, dict[str, float]]:
    if not rows:
        raise ValueError("NO_ELIGIBLE_HISTORY")
    fitted = {}
    for name in DIMENSIONS:
        values = [float(row[name]) for row in rows]
        if any(not math.isfinite(v) for v in values):
            raise ValueError(f"NON_FINITE_NORMALIZATION_INPUT:{name}")
        iqr = percentile(values, 0.75) - percentile(values, 0.25)
        if not math.isfinite(iqr) or iqr == 0:
            raise ValueError(f"ZERO_OR_INVALID_IQR:{name}")
        fitted[name] = {"median": median(values), "iqr": iqr}
    return fitted


def distance(
    current: Mapping[str, float],
    historical: Mapping[str, float],
    fitted: Mapping[str, Mapping[str, float]],
    weights: Mapping[str, float],
) -> tuple[float, dict[str, float]]:
    differences = {
        name: (float(current[name]) - float(historical[name]))
        / float(fitted[name]["iqr"])
        for name in DIMENSIONS
    }
    value = math.sqrt(
        sum(float(weights[name]) * delta * delta for name, delta in differences.items())
    )
    return value, differences


def wilson(positive: int, count: int, confidence: float = 0.95) -> list[float]:
    if count <= 0:
        raise ValueError("Wilson interval requires a positive count")
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    p = positive / count
    denominator = 1 + z * z / count
    center = (p + z * z / (2 * count)) / denominator
    margin = (
        z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / denominator
    )
    return [max(0.0, center - margin), min(1.0, center + margin)]


def horizon_statistics(
    returns: Sequence[float], baseline_returns: Sequence[float]
) -> dict[str, Any]:
    positives = sum(value > 0 for value in returns)
    baseline = sum(value > 0 for value in baseline_returns) / len(baseline_returns)
    probability = positives / len(returns)
    return {
        "sample_count": len(returns),
        "positive_count": positives,
        "positive_probability": probability,
        "median_return": median(returns),
        "p25_return": percentile(returns, 0.25),
        "wilson_interval": wilson(positives, len(returns)),
        "baseline_probability": baseline,
        "lift": probability - baseline,
    }


def match_snapshot(
    current: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    profile: Any,
    *,
    production: bool = True,
    query_cutoff: date | None = None,
) -> dict[str, Any]:
    if current.get("status") != "evaluable":
        return {
            "status": "not_evaluable",
            "reason_codes": list(current.get("invalid_reasons", ["CURRENT_SNAPSHOT_NOT_EVALUABLE"])),
            "candidate_count": 0,
            "usable_sample": 0,
            "required_sample": int(profile.config["minimum_sample"]),
        }
    threshold = profile.config["distance_threshold"]
    if threshold is None:
        return {
            "status": "threshold_required",
            "reason_codes": ["DISTANCE_THRESHOLD_NULL"],
            "action": "run calibration, freeze a numeric threshold, and complete final validation",
        }
    if production and profile.config["status"] != "approved":
        return {
            "status": "profile_not_approved",
            "reason_codes": ["EXACT_PROFILE_NOT_APPROVED"],
        }
    session = current["trading_session"]
    lower_year = session.year - int(profile.config["maximum_lookback_years"])
    eligible = []
    for row in candidates:
        if (
            row.get("symbol") != current.get("symbol")
            or row.get("profile_code") != profile.code
            or row.get("version") != profile.version
            or row.get("config_hash") != profile.config_hash
        ):
            continue
        if (
            row.get("timeframe") != "1d"
            or row.get("checkpoint") != "EOD"
            or row.get("status") != "evaluable"
        ):
            continue
        candidate_session = row["trading_session"]
        if not (
            date(lower_year, session.month, min(session.day, 28))
            <= candidate_session
            < session
        ):
            continue
        outcomes = row.get("outcomes", {})
        if any(
            h not in outcomes
            or outcomes[h].get("status") != "completed"
            or outcomes[h].get("target_session") > (query_cutoff or session)
            for h in (1, 3, 5)
        ):
            continue
        eligible.append(row)
    try:
        fitted = fit_median_iqr([row["dimensions"] for row in eligible])
    except ValueError as exc:
        return {
            "status": "not_evaluable",
            "reason_codes": [str(exc)],
            "candidate_count": len(eligible),
        }
    ranked: list[dict[str, Any]] = []
    for row in eligible:
        value, differences = distance(
            current["dimensions"], row["dimensions"], fitted, profile.weights
        )
        if value <= threshold:
            ranked.append(
                {
                    "snapshot": row,
                    "distance": value,
                    "similarity": math.exp(-value) * 100,
                    "normalized_differences": differences,
                }
            )
    ranked.sort(
        key=lambda item: (
            item["distance"],
            item["snapshot"]["trading_session"],
            item["snapshot"].get("id", ""),
        )
    )
    selected = ranked[: int(profile.config["top_k"])]
    required = int(profile.config["minimum_sample"])
    base = {
        "candidate_count": len(eligible),
        "usable_sample": len(selected),
        "required_sample": required,
        "normalization": fitted,
    }
    matches = [
        {
            "rank": rank,
            "snapshot_id": item["snapshot"].get("id"),
            "trading_session": item["snapshot"]["trading_session"],
            "distance": item["distance"],
            "similarity": item["similarity"],
            "normalized_differences": item["normalized_differences"],
            "outcomes": item["snapshot"]["outcomes"],
        }
        for rank, item in enumerate(selected, 1)
    ]
    if len(selected) < required:
        return {
            "status": "insufficient_sample",
            "reason_codes": ["MINIMUM_SAMPLE_NOT_MET"],
            **base,
            "matches": matches,
        }
    statistics = {}
    for horizon in (1, 3, 5):
        returns = [
            item["snapshot"]["outcomes"][horizon]["return_ratio"] for item in selected
        ]
        baseline_returns = [
            row["outcomes"][horizon]["return_ratio"] for row in eligible
        ]
        statistics[str(horizon)] = horizon_statistics(returns, baseline_returns)
    return {"status": "completed", **base, "statistics": statistics, "matches": matches}
