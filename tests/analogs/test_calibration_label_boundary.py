"""STRICT calibration label-boundary contract tests.

Synthetic and offline only: no SSI, Supabase, database, or network access.
These tests pin the HA-01 policy: calibration scoring accepts a label only when
its ``target_session <= training_end``; anything beyond the training end is
censored per horizon (never dropped or widening the match set), completed
outcomes with a missing/invalid ``target_session`` are not scored, boundaries
fail closed in both the CLI and direct calls, and every calibration route
carries a deterministic STRICT identity and reconcilable label accounting.

Non-calibration walk-forward output remains byte-compatible with the legacy
contract.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

import pytest

from src.research.analogs.profile import (
    AnalogProfile,
    config_hash,
    load_profile,
    load_source_profile,
)
from src.research.analogs.validation import (
    CALIBRATION_POLICY_MARKER,
    calibrate,
    walk_forward,
)

TRAINING_START = date(2026, 1, 5)
TRAINING_END = date(2026, 1, 30)
FINAL_TEST_START = date(2026, 2, 2)


def _profile(version: int = 1) -> AnalogProfile:
    source = load_source_profile("TPLUS_ANALOG_CORE_EOD", version)
    config = {
        **source.config,
        "distance_threshold": 999,
        "status": "approved",
        "minimum_sample": 2,
        "top_k": 2,
    }
    return AnalogProfile(config, config_hash(config))


def _dimensions(seed: int) -> dict[str, float]:
    return {
        name: float(seed * (index + 1))
        for index, name in enumerate(load_profile().weights)
    }


def _completed_outcomes(profile: AnalogProfile, session: date) -> dict:
    return {
        horizon: {
            "status": "completed",
            "target_session": session + timedelta(days=horizon),
            "return_ratio": 0.01 * horizon,
        }
        for horizon in profile.config["horizons"]
    }


def _snapshot(profile, index, session, *, outcomes=None):
    return {
        "id": f"snap-{index}",
        "profile_code": profile.code,
        "version": profile.version,
        "config_hash": profile.config_hash,
        "symbol": "SSI",
        "timeframe": "1d",
        "checkpoint": "EOD",
        "trading_session": session,
        "status": "evaluable",
        "dimensions": _dimensions(index + 1),
        "outcomes": outcomes if outcomes is not None else _completed_outcomes(profile, session),
    }


def _candidates(profile, count=4):
    return [
        _snapshot(profile, index, date(2025, 1, 1) + timedelta(days=index * 30))
        for index in range(count)
    ]


def _query(profile, session, targets):
    outcomes = {
        horizon: {
            "status": "completed",
            "target_session": targets[horizon],
            "return_ratio": 0.01 * horizon,
        }
        for horizon in profile.config["horizons"]
    }
    return _snapshot(profile, 20, session, outcomes=outcomes)


def _calibrate_kwargs(**overrides):
    kwargs = {
        "start": TRAINING_START,
        "end": TRAINING_END,
        "final_test_start": FINAL_TEST_START,
        "run_type": "calibration",
    }
    kwargs.update(overrides)
    return kwargs


def test_calibration_target_at_end_scored_and_beyond_end_censored():
    profile = _profile(1)
    candidates = _candidates(profile)
    query = _query(
        profile,
        TRAINING_END - timedelta(days=2),
        {
            1: TRAINING_END,                       # == training_end -> scored
            3: TRAINING_END + timedelta(days=1),   # > training_end, < final -> censored
            5: FINAL_TEST_START,                   # == final_test_start -> censored
        },
    )
    result = walk_forward(
        profile, candidates + [query], **_calibrate_kwargs()
    )
    accounting = result["label_accounting"]
    assert accounting[1]["scored"] == 1
    assert accounting[3]["censored"] == 1
    assert accounting[5]["censored"] == 1
    assert result["metrics"][1]["forecast_count"] == 1
    assert result["metrics"][3]["forecast_count"] == 0
    assert result["metrics"][5]["forecast_count"] == 0
    assert result["reason_counts"]["CURRENT_OUTCOME_CENSORED_H3"] == 1
    assert result["reason_counts"]["CURRENT_OUTCOME_CENSORED_H5"] == 1


def test_v2_only_h10_crosses_boundary():
    profile = _profile(2)
    candidates = _candidates(profile)
    query = _query(
        profile,
        TRAINING_END - timedelta(days=1),
        {
            1: TRAINING_END,        # == training_end -> scored
            3: TRAINING_END,        # == training_end -> scored
            5: TRAINING_END,        # == training_end -> scored
            10: FINAL_TEST_START,   # > training_end -> censored
        },
    )
    result = walk_forward(
        profile, candidates + [query], **_calibrate_kwargs()
    )
    accounting = result["label_accounting"]
    for horizon in (1, 3, 5):
        assert accounting[horizon]["scored"] == 1
        assert accounting[horizon]["censored"] == 0
    assert accounting[10]["censored"] == 1
    assert accounting[10]["scored"] == 0


def test_calibration_pending_missing_and_invalid_target_accounting():
    profile = _profile(1)
    candidates = _candidates(profile)
    query = _snapshot(
        profile,
        21,
        TRAINING_END - timedelta(days=5),
        outcomes={
            3: {"status": "pending", "reason": "TARGET_SESSION_NOT_YET_OBSERVABLE"},
            5: {"status": "completed", "target_session": None, "return_ratio": 0.05},
            # horizon 1 intentionally absent -> missing
        },
    )
    result = walk_forward(
        profile, candidates + [query], **_calibrate_kwargs()
    )
    accounting = result["label_accounting"]
    assert accounting[1]["missing"] == 1
    assert accounting[3]["pending"] == 1
    assert accounting[5]["invalid"] == 1
    assert result["reason_counts"]["CURRENT_OUTCOME_MISSING_H1"] == 1
    assert result["reason_counts"]["CURRENT_OUTCOME_PENDING_H3"] == 1
    assert (
        result["reason_counts"]["CURRENT_OUTCOME_H3:TARGET_SESSION_NOT_YET_OBSERVABLE"]
        == 1
    )
    assert result["reason_counts"]["CURRENT_OUTCOME_INVALID_TARGET_SESSION_H5"] == 1


def test_calibration_target_session_type_policy_date_datetime_string():
    profile = _profile(1)
    candidates = _candidates(profile)
    in_bound = TRAINING_END - timedelta(days=1)
    query = _snapshot(
        profile,
        22,
        TRAINING_END - timedelta(days=3),
        outcomes={
            1: {
                "status": "completed",
                "target_session": in_bound,
                "return_ratio": 0.01,
            },
            3: {
                "status": "completed",
                "target_session": datetime.combine(in_bound, time(17, 0)),
                "return_ratio": 0.03,
            },
            5: {
                "status": "completed",
                "target_session": in_bound.isoformat(),
                "return_ratio": 0.05,
            },
        },
    )
    result = walk_forward(
        profile, candidates + [query], **_calibrate_kwargs()
    )
    for horizon in (1, 3, 5):
        assert result["label_accounting"][horizon]["scored"] == 1
        assert result["metrics"][horizon]["forecast_count"] == 1


def test_calibration_datetime_string_beyond_end_censored_and_garbage_invalid():
    profile = _profile(1)
    candidates = _candidates(profile)
    beyond = TRAINING_END + timedelta(days=1)
    query = _snapshot(
        profile,
        23,
        TRAINING_END - timedelta(days=3),
        outcomes={
            1: {
                "status": "completed",
                "target_session": datetime.combine(beyond, time(9, 0)),
                "return_ratio": 0.01,
            },
            3: {
                "status": "completed",
                "target_session": beyond.isoformat(),
                "return_ratio": 0.03,
            },
            5: {
                "status": "completed",
                "target_session": "not-a-date",
                "return_ratio": 0.05,
            },
        },
    )
    result = walk_forward(
        profile, candidates + [query], **_calibrate_kwargs()
    )
    accounting = result["label_accounting"]
    assert accounting[1]["censored"] == 1
    assert accounting[3]["censored"] == 1
    assert accounting[5]["invalid"] == 1


def test_calibration_boundaries_fail_closed_on_direct_calls():
    profile = _profile(1)
    snapshots = _candidates(profile)

    with pytest.raises(ValueError, match="final-test"):
        walk_forward(
            profile, snapshots, start=TRAINING_START, end=TRAINING_END,
            run_type="calibration",
        )
    with pytest.raises(ValueError, match="start must not be after"):
        walk_forward(
            profile, snapshots, start=TRAINING_END, end=TRAINING_START,
            final_test_start=FINAL_TEST_START, run_type="calibration",
        )
    with pytest.raises(ValueError, match="final-test"):
        walk_forward(
            profile, snapshots, start=TRAINING_START, end=FINAL_TEST_START,
            final_test_start=FINAL_TEST_START, run_type="calibration",
        )
    with pytest.raises(ValueError, match="start must not be after"):
        calibrate(
            profile, snapshots, [0.5],
            training_start=TRAINING_END, training_end=TRAINING_START,
            final_test_start=FINAL_TEST_START,
        )
    with pytest.raises(ValueError, match="final-test"):
        calibrate(
            profile, snapshots, [0.5],
            training_start=TRAINING_START, training_end=FINAL_TEST_START,
            final_test_start=FINAL_TEST_START,
        )


def test_both_calibration_routes_carry_strict_identity():
    profile = _profile(1)
    candidates = _candidates(profile)
    query = _snapshot(profile, 24, TRAINING_END - timedelta(days=2))
    snapshots = candidates + [query]

    direct = walk_forward(profile, snapshots, **_calibrate_kwargs())
    via_threshold = calibrate(
        profile, snapshots, [0.5, 1.0],
        training_start=TRAINING_START, training_end=TRAINING_END,
        final_test_start=FINAL_TEST_START,
    )

    for evidence in (direct, via_threshold):
        assert evidence["policy"]["marker"] == CALIBRATION_POLICY_MARKER
        assert evidence["policy"]["version"]
        assert evidence["boundaries"]["training_start"] == TRAINING_START.isoformat()
        assert evidence["boundaries"]["training_end"] == TRAINING_END.isoformat()
        assert (
            evidence["boundaries"]["final_test_start"]
            == FINAL_TEST_START.isoformat()
        )
        assert evidence["profile_identity"]["code"] == "TPLUS_ANALOG_CORE_EOD"
        assert evidence["profile_identity"]["version"] == 1
        assert evidence["profile_identity"]["config_hash"] == profile.config_hash
        assert len(evidence["code_identity"]) == 64
        assert len(evidence["data_identity"]) == 64
        assert len(evidence["evidence_identity"]) == 64

    # Same data/boundaries/profile => identical evidence identity across routes.
    assert direct["evidence_identity"] == via_threshold["evidence_identity"]


def test_label_accounting_reconciles_with_eligible_forecasts():
    profile = _profile(2)
    candidates = _candidates(profile)
    queries = [
        _snapshot(profile, 30, TRAINING_END - timedelta(days=8)),
        _snapshot(
            profile, 31, TRAINING_END - timedelta(days=5),
            outcomes={
                1: {"status": "completed", "target_session": TRAINING_END, "return_ratio": 0.01},
                3: {"status": "pending", "reason": "TARGET_SESSION_NOT_YET_OBSERVABLE"},
                5: {"status": "completed", "target_session": None, "return_ratio": 0.05},
                10: {"status": "completed", "target_session": FINAL_TEST_START, "return_ratio": 0.10},
            },
        ),
        _snapshot(profile, 32, TRAINING_END - timedelta(days=2)),
    ]
    snapshots = candidates + queries
    result = walk_forward(profile, snapshots, **_calibrate_kwargs())

    assert result["query_count"] == len(queries)
    assert result["eligible_forecasts"] == len(queries)
    assert result["not_evaluable_queries"] == 0

    for horizon in profile.config["horizons"]:
        total = sum(result["label_accounting"][horizon].values())
        assert total == result["eligible_forecasts"]


def test_calibration_output_is_deterministic_and_order_independent():
    profile = _profile(1)
    candidates = _candidates(profile)
    query = _snapshot(profile, 33, TRAINING_END - timedelta(days=2))
    snapshots = candidates + [query]

    first = walk_forward(profile, snapshots, **_calibrate_kwargs())
    second = walk_forward(
        profile, list(reversed(snapshots)), **_calibrate_kwargs()
    )
    assert first == second


def test_identity_changes_on_label_change_but_stable_for_same_data():
    profile = _profile(1)
    candidates = _candidates(profile)
    query = _snapshot(profile, 34, TRAINING_END - timedelta(days=2))
    snapshots = candidates + [query]

    baseline = walk_forward(profile, snapshots, **_calibrate_kwargs())

    mutated = deepcopy(snapshots)
    mutated[-1]["outcomes"][1]["return_ratio"] = 0.999
    changed = walk_forward(profile, mutated, **_calibrate_kwargs())
    assert changed["data_identity"] != baseline["data_identity"]
    assert changed["evidence_identity"] != baseline["evidence_identity"]

    same = walk_forward(profile, deepcopy(snapshots), **_calibrate_kwargs())
    assert same["data_identity"] == baseline["data_identity"]
    assert same["evidence_identity"] == baseline["evidence_identity"]

    assert baseline["code_identity"] == changed["code_identity"] == same["code_identity"]


def test_non_calibration_output_keeps_legacy_shape_and_scoring():
    profile = _profile(1)
    candidates = _candidates(profile)
    query = _snapshot(profile, 35, TRAINING_END - timedelta(days=2))
    # A completed outcome beyond the training end must still be scored for
    # validation/final (no STRICT censor on the legacy path).
    query["outcomes"][5]["target_session"] = FINAL_TEST_START
    session = TRAINING_END - timedelta(days=2)
    legacy_keys = {
        "status", "run_type", "range", "query_count", "coverage",
        "insufficient_sample_count", "metrics", "reason_counts",
    }

    result = walk_forward(
        profile, candidates + [query], start=session, end=session,
        run_type="validation",
    )
    assert result["run_type"] == "validation"
    assert set(result) == legacy_keys
    assert result["metrics"][5]["forecast_count"] == 1
    assert "policy" not in result and "label_accounting" not in result
    assert "evidence_identity" not in result and "code_identity" not in result

    final = walk_forward(
        profile, candidates + [query], start=session, end=session,
        run_type="final",
    )
    assert final["run_type"] == "final"
    assert set(final) == legacy_keys
    assert final["metrics"][5]["forecast_count"] == 1


def test_cli_calibration_boundaries_fail_closed_before_db(monkeypatch):
    import src.research.analogs.cli as cli

    def refuse_repository(*args, **kwargs):
        raise AssertionError("repository must not be constructed for invalid boundaries")

    monkeypatch.setattr(cli, "repository_from_environment", refuse_repository)

    def make_args(*, from_date="05/01/2026", to_date="30/01/2026", final_test_start="02/02/2026"):
        return SimpleNamespace(
            analog_command="validate",
            profile="TPLUS_ANALOG_CORE_EOD",
            version=1,
            config_hash=None,
            run_type="calibration",
            symbols=["SSI"],
            from_date=from_date,
            to_date=to_date,
            final_test_start=final_test_start,
            thresholds=[],
        )

    with pytest.raises(ValueError, match="final-test-start"):
        cli.run(make_args(final_test_start=None))
    with pytest.raises(ValueError, match="start must not be after"):
        cli.run(make_args(from_date="30/01/2026", to_date="05/01/2026"))
    with pytest.raises(ValueError, match="final-test"):
        cli.run(make_args(to_date="02/02/2026", final_test_start="02/02/2026"))


def test_cli_calibration_no_threshold_route_carries_strict_marker(monkeypatch):
    import src.research.analogs.cli as cli

    profile = _profile(1)
    candidates = _candidates(profile)
    query = _snapshot(profile, 36, TRAINING_END - timedelta(days=2))

    repo = SimpleNamespace()
    monkeypatch.setattr(cli, "repository_from_environment", lambda: repo)
    monkeypatch.setattr(
        cli, "exact_profile",
        lambda repository, code, version, requested_hash=None: (
            profile, {"status": "approved"},
        ),
    )
    monkeypatch.setattr(
        cli, "hydrate_evidence",
        lambda repository, p, symbol, session: (query, candidates),
    )

    args = SimpleNamespace(
        analog_command="validate",
        profile="TPLUS_ANALOG_CORE_EOD",
        version=1,
        config_hash=None,
        run_type="calibration",
        symbols=["SSI"],
        from_date="05/01/2026",
        to_date="30/01/2026",
        final_test_start="02/02/2026",
        thresholds=[],
    )
    result = cli.run(args)
    assert result["policy"]["marker"] == CALIBRATION_POLICY_MARKER
    assert result["run_type"] == "calibration"
    assert result["label_accounting"][1]["scored"] == 1
    assert result["label_accounting"][3]["censored"] == 1
    assert result["label_accounting"][5]["censored"] == 1
