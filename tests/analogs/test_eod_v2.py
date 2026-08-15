from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.analogs.core import match_snapshot, resolve_outcomes
from src.analogs.pipeline import build_history
from src.analogs.profile import (
    AnalogProfile,
    config_hash,
    load_profile,
    load_source_profile,
    validate_profile,
)
from src.analogs.runtime import exact_profile
from src.analogs.validation import walk_forward


def test_v1_and_v2_exact_deterministic_profiles():
    v1_bytes = Path("src/analogs/profiles/tplus_analog_core_eod_v1.json").read_bytes()
    v1 = load_source_profile("TPLUS_ANALOG_CORE_EOD", 1)
    v2 = load_source_profile("TPLUS_ANALOG_CORE_EOD", 2)
    assert v1.config["horizons"] == [1, 3, 5]
    assert v2.config["horizons"] == [1, 3, 5, 10]
    assert v1.config_hash == config_hash(deepcopy(v1.config))
    assert v2.config_hash == config_hash(deepcopy(v2.config)) != v1.config_hash
    assert (
        v1_bytes
        == Path("src/analogs/profiles/tplus_analog_core_eod_v1.json").read_bytes()
    )


@pytest.mark.parametrize("horizons", ([1, 5, 3], [1, 3, 10], [1, 3, 5, 7]))
def test_unsupported_or_unordered_v2_horizons_rejected(horizons):
    config = deepcopy(load_source_profile("TPLUS_ANALOG_CORE_EOD", 2).config)
    config["horizons"] = horizons
    with pytest.raises(ValueError, match="horizons must"):
        validate_profile(config)


def test_exact_source_resolution_has_no_latest_fallback_or_hash_substitution():
    with pytest.raises(ValueError, match="SOURCE_PROFILE_NOT_FOUND"):
        load_source_profile("TPLUS_ANALOG_CORE_EOD", 3)
    with pytest.raises(ValueError, match="SOURCE_PROFILE_CONFIG_HASH_MISMATCH"):
        load_source_profile("TPLUS_ANALOG_CORE_EOD", 2, "0" * 64)

    v2 = load_source_profile("TPLUS_ANALOG_CORE_EOD", 2)
    row = {"config_hash": v2.config_hash, "configuration": v2.config, "status": "draft"}
    repo = type("Repo", (), {"get_profile": lambda self, code, version: row})()
    resolved, _ = exact_profile(repo, v2.code, 2, v2.config_hash)
    assert resolved.version == 2


def observed_sessions(count=12):
    # Explicit gaps cover weekends/holidays; only these canonical observations count.
    return [date(2026, 1, 2) + timedelta(days=i * 2 + (i // 4)) for i in range(count)]


def test_h10_is_tenth_observed_session_pending_and_invalid_is_unavailable():
    sessions = observed_sessions()
    closes = {session: 100 + index for index, session in enumerate(sessions)}
    complete = resolve_outcomes(sessions[0], 100, sessions, closes, [1, 3, 5, 10])
    assert complete[-1]["target_session"] == sessions[10]
    assert complete[-1]["return_ratio"] == pytest.approx(0.10)
    assert (
        resolve_outcomes(sessions[0], 100, sessions[:10], closes, [10])[0]["status"]
        == "pending"
    )
    closes[sessions[10]] = float("nan")
    unavailable = resolve_outcomes(sessions[0], 100, sessions, closes, [10])[0]
    assert (
        unavailable["status"] == "unavailable"
        and unavailable["reason"] == "INVALID_CLOSE"
    )


def feature_rows(sessions):
    rows = []
    for index, session in enumerate(sessions):
        rows.append(
            {
                "symbol": "SSI",
                "timeframe": "1d",
                "trading_session": session,
                "close": 100 + index,
                "low": 99 + index,
                "high": 102 + index,
                "ema20": 90 + index,
                "ema50": 80 + index,
                "rsi14": 50 + index,
                "macd_histogram": 1,
                "high_20_bars": 110 + index,
                "volume_ratio": 1 + index / 10,
                "value_ratio": 1 + index / 20,
            }
        )
    return rows


def test_evaluable_v2_snapshot_builds_four_outcome_records():
    profile = load_source_profile("TPLUS_ANALOG_CORE_EOD", 2)
    sessions = observed_sessions(16)
    features = feature_rows(sessions)
    closes = {("SSI", row["trading_session"]): row["close"] for row in features}
    result = build_history(
        profile,
        features,
        sessions,
        closes,
        symbols=["SSI"],
        start=sessions[5],
        end=sessions[5],
        mode="full",
    )
    assert [row["horizon_sessions"] for row in result["outcomes"]] == [1, 3, 5, 10]


def approved_v2():
    source = load_source_profile("TPLUS_ANALOG_CORE_EOD", 2)
    config = {
        **source.config,
        "distance_threshold": 999,
        "status": "approved",
        "minimum_sample": 2,
        "top_k": 2,
    }
    return AnalogProfile(config, config_hash(config))


def dimensions(seed):
    return {
        name: seed * (index + 1) for index, name in enumerate(load_profile().weights)
    }


def snapshot(profile, index, session, *, h10_target=None):
    return {
        "id": str(index),
        "profile_code": profile.code,
        "version": profile.version,
        "config_hash": profile.config_hash,
        "symbol": "SSI",
        "timeframe": "1d",
        "checkpoint": "EOD",
        "trading_session": session,
        "status": "evaluable",
        "dimensions": dimensions(index + 1),
        "outcomes": {
            h: {
                "status": "completed",
                "target_session": (
                    h10_target
                    if h == 10 and h10_target
                    else session + timedelta(days=h)
                ),
                "return_ratio": 0.01 * h,
            }
            for h in profile.config["horizons"]
        },
    }


def test_v2_h10_observability_controls_candidates_statistics_and_validation_reasons():
    profile = approved_v2()
    cutoff = date(2026, 1, 31)
    candidates = [
        snapshot(profile, i, date(2025, 1, 1) + timedelta(days=i * 20))
        for i in range(4)
    ]
    leaked = deepcopy(candidates[-1])
    leaked.update(id="future-h10", dimensions=dimensions(10**9))
    leaked["outcomes"][10]["target_session"] = cutoff + timedelta(days=1)
    current = snapshot(profile, 20, cutoff)
    result = match_snapshot(
        current, candidates + [leaked], profile, production=False, query_cutoff=cutoff
    )
    assert result["status"] == "completed"
    assert set(result["statistics"]) == {"1", "3", "5", "10"}
    assert "future-h10" not in {row["snapshot_id"] for row in result["matches"]}

    current["outcomes"][10] = {
        "status": "pending",
        "reason": "TARGET_SESSION_NOT_YET_OBSERVABLE",
    }
    evidence = walk_forward(profile, candidates + [current], start=cutoff, end=cutoff)
    assert evidence["metrics"].keys() >= {1, 3, 5}
    assert evidence["reason_counts"]["CURRENT_OUTCOME_PENDING_H10"] == 1
    assert (
        evidence["reason_counts"][
            "CURRENT_OUTCOME_H10:TARGET_SESSION_NOT_YET_OBSERVABLE"
        ]
        == 1
    )


def test_v1_completed_statistics_remain_three_horizons():
    source = load_source_profile("TPLUS_ANALOG_CORE_EOD", 1)
    config = {
        **source.config,
        "distance_threshold": 999,
        "status": "approved",
        "minimum_sample": 2,
        "top_k": 2,
    }
    profile = AnalogProfile(config, config_hash(config))
    cutoff = date(2026, 1, 31)
    candidates = [
        snapshot(profile, i, date(2025, 1, 1) + timedelta(days=i * 20))
        for i in range(4)
    ]
    result = match_snapshot(
        snapshot(profile, 20, cutoff), candidates, profile, query_cutoff=cutoff
    )
    assert set(result["statistics"]) == {"1", "3", "5"}
