from copy import deepcopy
from datetime import date, timedelta
import math
import pytest

from src.analogs.core import (
    analog_quality,
    build_dimensions,
    distance,
    fit_median_iqr,
    horizon_statistics,
    match_snapshot,
    resolve_outcomes,
)
from src.analogs.profile import (
    AnalogProfile,
    config_hash,
    load_profile,
    validate_profile,
)
from src.analogs.service import review_profile
from src.analogs.validation import calibrate


def feature(**updates):
    row = {
        "close": 110,
        "low": 100,
        "high": 120,
        "ema20": 100,
        "ema50": 80,
        "rsi14": 55,
        "macd_histogram": 2.2,
        "high_20_bars": 125,
        "volume_ratio": 1.5,
        "value_ratio": 0.75,
    }
    row.update(updates)
    return row


def test_all_dimensions_and_decimal_units():
    result = build_dimensions(feature(), [80, 90, 95, 100, 105])
    assert result["status"] == "evaluable"
    assert result["dimensions"] == pytest.approx(
        {
            "return_5d": 0.375,
            "price_vs_ema20_pct": 0.1,
            "ema20_vs_ema50_pct": 0.25,
            "rsi14": 55,
            "macd_histogram_pct": 0.02,
            "distance_to_high20_pct": -0.12,
            "volume_ratio": 1.5,
            "value_ratio": 0.75,
            "close_position_in_candle": 0.5,
        }
    )


@pytest.mark.parametrize(
    ("updates", "history", "reason"),
    [
        ({"ema20": None}, [1] * 5, "MISSING_EMA20"),
        ({"ema50": 0}, [1] * 5, "ZERO_DENOMINATOR_EMA20_VS_EMA50"),
        ({"high": 100, "low": 100}, [1] * 5, "ZERO_CANDLE_RANGE"),
        ({"rsi14": math.nan}, [1] * 5, "NON_FINITE_RSI14"),
        ({"close": math.inf}, [1] * 5, "NON_FINITE_CLOSE"),
        ({}, [1] * 4, "INSUFFICIENT_FIVE_SESSION_HISTORY"),
    ],
)
def test_invalid_dimensions_are_not_zero(updates, history, reason):
    result = build_dimensions(feature(**updates), history)
    assert result["status"] == "not_evaluable" and reason in result["invalid_reasons"]
    assert any(value is None for value in result["dimensions"].values())


def test_profile_hash_and_weights():
    profile = load_profile()
    assert profile.config_hash == config_hash(deepcopy(profile.config))
    changed = deepcopy(profile.config)
    changed["top_k"] = 31
    assert config_hash(changed) != profile.config_hash
    bad = deepcopy(profile.config)
    bad["dimensions"][0]["weight"] += 0.01
    with pytest.raises(ValueError, match="total"):
        validate_profile(bad)


def test_trading_session_outcomes_pending_complete_unavailable_and_gap():
    sessions = [
        date(2026, 1, 2),
        date(2026, 1, 5),
        date(2026, 1, 7),
        date(2026, 1, 8),
        date(2026, 1, 9),
        date(2026, 1, 12),
    ]
    closes = {
        sessions[1]: 101,
        sessions[2]: None,
        sessions[3]: 103,
        sessions[4]: 104,
        sessions[5]: 105,
    }
    rows = resolve_outcomes(
        sessions[0],
        100,
        sessions,
        closes,
        cutoff=sessions[3],
        unavailable_sessions=[sessions[2]],
    )
    assert (
        rows[0]["target_session"] == date(2026, 1, 5)
        and rows[0]["status"] == "completed"
    )
    assert (
        rows[1]["target_session"] == date(2026, 1, 8)
        and rows[1]["status"] == "completed"
    )
    assert rows[2]["status"] == "pending"
    unavailable = resolve_outcomes(
        sessions[0], 100, sessions, closes, cutoff=sessions[-1]
    )[1]
    assert unavailable["status"] == "completed"  # H+3, not next observed missing row


def dims(seed):
    return {name: seed * (i + 1) for i, name in enumerate(load_profile().weights)}


def candidate(i, symbol="SSI", outcome_target=None):
    session = date(2020, 1, 1) + timedelta(days=i * 30)
    target = outcome_target or session + timedelta(days=10)
    return {
        "id": str(i),
        "profile_code": "TPLUS_ANALOG_CORE_EOD",
        "version": 1,
        "config_hash": "",
        "symbol": symbol,
        "timeframe": "1d",
        "checkpoint": "EOD",
        "trading_session": session,
        "status": "evaluable",
        "dimensions": dims(i + 1),
        "outcomes": {
            h: {
                "status": "completed",
                "target_session": target,
                "return_ratio": (-1 if i % 3 == 0 else 1) * 0.01 * h,
            }
            for h in (1, 3, 5)
        },
    }


def approved_profile(threshold=999):
    p = load_profile()
    config = {**p.config, "distance_threshold": threshold, "status": "approved"}
    return AnalogProfile(config, config_hash(config))


def prepare(profile, count=60):
    rows = [candidate(i) for i in range(count)]
    for row in rows:
        row["config_hash"] = profile.config_hash
    current = candidate(80)
    current.update(
        config_hash=profile.config_hash,
        trading_session=date(2026, 1, 1),
        dimensions=dims(36),
    )
    return current, rows


def test_same_symbol_identity_five_year_and_future_observability():
    p = approved_profile()
    current, rows = prepare(p)
    other = candidate(34, "HPG")
    other.update(id="other", config_hash=p.config_hash)
    rows.append(other)
    wrong = deepcopy(rows[-2])
    wrong["id"] = "wrong"
    wrong["checkpoint"] = "13:30"
    rows.append(wrong)
    future = deepcopy(rows[-3])
    future["id"] = "future"
    future["outcomes"][5]["target_session"] = date(2026, 2, 1)
    rows.append(future)
    result = match_snapshot(current, rows, p, query_cutoff=current["trading_session"])
    assert result["status"] == "completed" and result["usable_sample"] == 30
    ids = {m["snapshot_id"] for m in result["matches"]}
    assert "future" not in ids and "wrong" not in ids and other["id"] not in ids
    assert all(
        date(2021, 1, 1) <= next(r for r in rows if r["id"] == i)["trading_session"]
        for i in ids
    )


def test_future_outlier_cannot_change_normalization():
    p = approved_profile()
    current, rows = prepare(p)
    base_result = match_snapshot(
        current, rows, p, query_cutoff=current["trading_session"]
    )
    base = base_result["normalization"]
    outlier = candidate(100)
    outlier.update(
        id="outlier",
        config_hash=p.config_hash,
        trading_session=date(2027, 1, 1),
        dimensions=dims(1e9),
    )
    leaked_result = match_snapshot(
        current, rows + [outlier], p, query_cutoff=current["trading_session"]
    )
    assert base == leaked_result["normalization"]
    assert base_result["analog_quality"] == leaked_result["analog_quality"]


def test_zero_iqr_threshold_top30_and_insufficient_no_padding():
    p = approved_profile()
    current, rows = prepare(p)
    flat = deepcopy(rows[:30])
    [row.update(dimensions=dims(1)) for row in flat]
    assert "ZERO_OR_INVALID_IQR" in match_snapshot(current, flat, p)["reason_codes"][0]
    small = approved_profile(0.00001)
    current, rows = prepare(small)
    result = match_snapshot(current, rows, small)
    assert result["status"] == "completed" and result["usable_sample"] == 30
    assert result["analog_quality"]["d_k"] == result["matches"][29]["distance"]


def test_distance_similarity_statistics():
    rows = [dims(1), dims(2), dims(3), dims(4)]
    fitted = fit_median_iqr(rows)
    value, diffs = distance(rows[1], rows[2], fitted, {name: 1 / 9 for name in dims(1)})
    assert value > 0 and set(diffs) == set(dims(1))
    stats = horizon_statistics([-0.1, 0.1, 0.2], [-0.2, -0.1, 0.1, 0.2])
    assert stats["positive_probability"] == pytest.approx(2 / 3)
    assert (
        stats["p25_return"] == 0
        and stats["median_return"] == 0.1
        and stats["baseline_probability"] == 0.5
        and stats["lift"] == pytest.approx(1 / 6)
    )
    assert 0 <= stats["wilson_interval"][0] < stats["wilson_interval"][1] <= 1


def test_null_threshold_is_not_a_matching_or_approval_gate():
    draft = load_profile()
    current, rows = prepare(draft)
    assert (
        match_snapshot(current, rows, draft, production=False)["status"] == "completed"
    )
    repo = type("Repo", (), {"insert_review": lambda self, row: row})()
    profile_row = {
        "profile_code": draft.code,
        "version": 1,
        "config_hash": draft.config_hash,
        "configuration": draft.config,
    }
    validation = {
        "id": "v",
        "config_hash": draft.config_hash,
        "run_type": "final",
        "status": "completed",
    }
    assert (
        review_profile(
            repo,
            profile_row,
            validation,
            reviewer="owner",
            decision="approve",
            reason="evidence",
            apply=True,
        )["status"]
        == "recorded"
    )
    with pytest.raises(ValueError, match="exact completed"):
        review_profile(
            repo,
            profile_row,
            {**validation, "config_hash": "bad"},
            reviewer="owner",
            decision="reject",
            reason="bad",
            apply=True,
        )


def test_top_k_is_configurable_and_insufficient_requires_the_full_k():
    base = approved_profile()
    config = {**base.config, "top_k": 7, "minimum_sample": 7}
    profile = AnalogProfile(config, config_hash(config))
    current, rows = prepare(profile, count=60)
    result = match_snapshot(
        current, rows, profile, production=False, calibration_radii=[]
    )
    assert result["status"] == "completed" and result["usable_sample"] == 7
    assert result["analog_quality"]["sample_size"] == 7
    assert result["analog_quality"]["d_k"] == result["matches"][6]["distance"]
    insufficient = match_snapshot(
        current, rows[13:19], profile, production=False, calibration_radii=[]
    )
    assert insufficient["status"] == "insufficient_sample"
    assert insufficient["analog_quality"]["quality_bucket"] == "unknown"


def test_top_k_order_is_deterministic_and_legacy_threshold_does_not_filter():
    profile = approved_profile(0)
    current, rows = prepare(profile, count=60)
    rows[34]["dimensions"] = deepcopy(rows[35]["dimensions"])
    result = match_snapshot(
        current, list(reversed(rows)), profile, production=False, calibration_radii=[]
    )
    assert result["status"] == "completed"
    assert [m["distance"] for m in result["matches"]] == sorted(
        m["distance"] for m in result["matches"]
    )
    tied = [
        m
        for m in result["matches"]
        if m["distance"]
        == next(x["distance"] for x in result["matches"] if x["snapshot_id"] == "34")
    ]
    assert [m["trading_session"] for m in tied] == sorted(
        m["trading_session"] for m in tied
    )
    assert any(m["distance"] > 0 for m in result["matches"])


def test_analog_quality_statistics_boundaries_warnings_and_unknown():
    distances = list(range(1, 31))
    unknown = analog_quality(distances, 30, [30] * 19)
    assert (
        unknown["quality_bucket"] == "unknown" and unknown["radius_percentile"] is None
    )
    assert unknown["median_distance"] == 15.5
    assert unknown["p90_distance"] == pytest.approx(27.1)
    assert analog_quality(distances, 30, [30] * 20)["quality_bucket"] == "good"
    assert (
        analog_quality(distances, 30, [10] * 10 + [20] * 4 + [30] * 6)["quality_bucket"]
        == "usable"
    )
    assert (
        analog_quality(distances, 30, [10] * 10 + [20] * 5 + [30] * 5)["quality_bucket"]
        == "weak"
    )
    assert (
        analog_quality(distances, 30, list(range(1, 21)))["quality_bucket"]
        == "out_of_distribution"
    )


def test_out_of_distribution_match_keeps_outcomes_and_adds_warning():
    profile = approved_profile(0)
    current, rows = prepare(profile)
    result = match_snapshot(
        current,
        rows,
        profile,
        production=False,
        calibration_radii=[0.0001] * 20,
    )
    assert result["status"] == "completed" and result["statistics"]
    assert result["analog_quality"]["quality_bucket"] == "out_of_distribution"
    assert result["warnings"] == ["ANALOG_QUALITY_OUT_OF_DISTRIBUTION"]


def test_calibration_final_test_isolation():
    p = load_profile()
    _, rows = prepare(p)
    artifact = calibrate(
        p,
        rows,
        [0.5, 1.0],
        training_start=date(2020, 1, 1),
        training_end=date(2023, 1, 1),
        final_test_start=date(2024, 1, 1),
    )
    assert (
        not artifact["mutated_profile"]
        and not artifact["qualifies_for_approval"]
        and len(artifact["candidates"]) == 2
    )
    with pytest.raises(ValueError, match="final-test"):
        calibrate(
            p,
            rows,
            [1],
            training_start=date(2020, 1, 1),
            training_end=date(2024, 1, 1),
            final_test_start=date(2024, 1, 1),
        )
