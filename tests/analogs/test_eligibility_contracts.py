"""Eligibility contract tests for same-symbol EOD analog matching.

Synthetic and offline only: no SSI, Supabase, database, or network access.
Socket egress is blocked for this module so a regression that starts calling an
external client fails loudly instead of silently reaching a real endpoint.
"""

from __future__ import annotations

import socket
from datetime import date, timedelta

import pytest

from src.research.analogs.core import DIMENSIONS, match_snapshot
from src.research.analogs.profile import load_profile


CURRENT_SESSION = date(2026, 1, 30)
BOUNDARY_SESSION = date(2025, 12, 1)


@pytest.fixture(autouse=True)
def blocked_network(monkeypatch):
    """Refuse any socket egress while these contract tests run."""

    def refuse(*args, **kwargs):
        raise AssertionError("network access is forbidden in eligibility tests")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


@pytest.fixture(scope="module")
def profile():
    """Exact source-controlled profile; it stays draft, so queries pass production=False."""
    return load_profile()


def _top_k(profile):
    return int(profile.config["top_k"])


def _dimensions(seed):
    return {name: float(seed * (index + 1)) for index, name in enumerate(DIMENSIONS)}


def _returns(profile, index, magnitude=0.01):
    return {
        horizon: (magnitude if index % 2 == 0 else -magnitude) * horizon
        for horizon in profile.config["horizons"]
    }


def _candidate(profile, index, session, *, dimensions_seed=None, returns=None):
    return {
        "id": f"snap-{index}",
        "profile_code": profile.code,
        "version": profile.version,
        "config_hash": profile.config_hash,
        "symbol": "SSI",
        "timeframe": profile.config["timeframe"],
        "checkpoint": profile.config["checkpoint"],
        "trading_session": session,
        "status": "evaluable",
        "dimensions": _dimensions(
            index + 1 if dimensions_seed is None else dimensions_seed
        ),
        "outcomes": {
            horizon: {
                "status": "completed",
                "target_session": session + timedelta(days=horizon),
                "return_ratio": (returns or {}).get(horizon, 0.01 * horizon),
            }
            for horizon in profile.config["horizons"]
        },
    }


def _history(profile, count):
    """Deterministic past candidates, all inside the five-year lookback window."""
    return [
        _candidate(
            profile,
            index,
            date(2024, 1, 2) + timedelta(days=index * 10),
            returns=_returns(profile, index),
        )
        for index in range(count)
    ]


def _current(profile):
    row = _candidate(profile, "current", CURRENT_SESSION, dimensions_seed=40)
    # Outcomes describe the session under analysis, not candidate eligibility.
    row["outcomes"] = {}
    return row


@pytest.mark.parametrize("horizon", (1, 3, 5))
def test_target_session_at_cutoff_is_eligible_but_one_session_later_is_not(
    profile, horizon
):
    current = _current(profile)
    history = _history(profile, _top_k(profile) - 1)

    def evaluate(target_session):
        boundary = _candidate(profile, "boundary", BOUNDARY_SESSION, dimensions_seed=40)
        boundary["outcomes"][horizon]["target_session"] = target_session
        return match_snapshot(
            current,
            history + [boundary],
            profile,
            production=False,
            query_cutoff=CURRENT_SESSION,
        )

    inclusive = evaluate(CURRENT_SESSION)
    assert inclusive["status"] == "completed"
    assert inclusive["candidate_count"] == _top_k(profile)
    assert "snap-boundary" in {
        match["snapshot_id"] for match in inclusive["matches"]
    }
    assert inclusive["statistics"][str(horizon)]["sample_count"] == _top_k(profile)

    later = evaluate(CURRENT_SESSION + timedelta(days=1))
    assert later["status"] == "insufficient_sample"
    assert later["candidate_count"] == _top_k(profile) - 1
    assert "snap-boundary" not in {match["snapshot_id"] for match in later["matches"]}
    assert later["reason_codes"] == ["MINIMUM_SAMPLE_NOT_MET"]


@pytest.mark.parametrize("breakage", ("pending", "missing"))
def test_one_incomplete_horizon_excludes_the_entire_candidate(profile, breakage):
    current = _current(profile)
    history = _history(profile, _top_k(profile))
    control = match_snapshot(
        current, history, profile, production=False, query_cutoff=CURRENT_SESSION
    )
    assert control["status"] == "completed"

    last_horizon = profile.config["horizons"][-1]
    broken = _candidate(profile, "broken", BOUNDARY_SESSION, dimensions_seed=40)
    # Extreme returns on the completed horizons must not enter any statistic.
    for horizon in profile.config["horizons"]:
        broken["outcomes"][horizon]["return_ratio"] = 9.0
    if breakage == "pending":
        broken["outcomes"][last_horizon] = {
            "status": "pending",
            "reason": "TARGET_SESSION_NOT_YET_OBSERVABLE",
        }
    else:
        broken["outcomes"].pop(last_horizon)

    result = match_snapshot(
        current,
        history + [broken],
        profile,
        production=False,
        query_cutoff=CURRENT_SESSION,
    )
    assert result["candidate_count"] == _top_k(profile)
    assert "snap-broken" not in {match["snapshot_id"] for match in result["matches"]}
    assert result["statistics"] == control["statistics"]
    for horizon in profile.config["horizons"]:
        assert result["statistics"][str(horizon)]["sample_count"] == _top_k(profile)

    repaired = _candidate(profile, "broken", BOUNDARY_SESSION, dimensions_seed=40)
    repaired_result = match_snapshot(
        current,
        history + [repaired],
        profile,
        production=False,
        query_cutoff=CURRENT_SESSION,
    )
    assert repaired_result["candidate_count"] == _top_k(profile) + 1
    assert "snap-broken" in {
        match["snapshot_id"] for match in repaired_result["matches"]
    }


IDENTITY_MISMATCHES = (
    ("symbol", "HPG"),
    ("profile_code", "TPLUS_ANALOG_CORE_EOD_ALT"),
    ("version", 2),
    ("config_hash", "0" * 64),
    ("timeframe", "60m"),
    ("checkpoint", "13:30"),
)


@pytest.mark.parametrize(("field", "value"), IDENTITY_MISMATCHES)
def test_candidate_identity_must_match_the_exact_profile(profile, field, value):
    current = _current(profile)
    history = _history(profile, _top_k(profile) - 1)
    exact = _candidate(profile, "exact", BOUNDARY_SESSION, dimensions_seed=40)
    mutated = _candidate(profile, "mutated", BOUNDARY_SESSION, dimensions_seed=40)
    mutated[field] = value
    assert mutated[field] != exact[field]

    accepted = match_snapshot(
        current,
        history + [exact],
        profile,
        production=False,
        query_cutoff=CURRENT_SESSION,
    )
    assert accepted["status"] == "completed"
    assert "snap-exact" in {match["snapshot_id"] for match in accepted["matches"]}

    rejected = match_snapshot(
        current,
        history + [mutated],
        profile,
        production=False,
        query_cutoff=CURRENT_SESSION,
    )
    assert rejected["status"] == "insufficient_sample"
    assert rejected["candidate_count"] == _top_k(profile) - 1
    assert "snap-mutated" not in {
        match["snapshot_id"] for match in rejected["matches"]
    }


def test_current_and_future_sessions_stay_out_of_normalization_and_statistics(
    profile,
):
    current = _current(profile)
    history = _history(profile, _top_k(profile))
    control = match_snapshot(
        current, history, profile, production=False, query_cutoff=CURRENT_SESSION
    )
    assert control["status"] == "completed"

    def leaky(index, session):
        row = _candidate(profile, index, session, dimensions_seed=40)
        for horizon in profile.config["horizons"]:
            # Targets sit inside the observable window so only the session bound
            # can keep this row out of the eligible set.
            row["outcomes"][horizon]["target_session"] = CURRENT_SESSION
            row["outcomes"][horizon]["return_ratio"] = 5.0
        return row

    leaked = match_snapshot(
        current,
        history
        + [
            leaky("leak-current", CURRENT_SESSION),
            leaky("leak-future", CURRENT_SESSION + timedelta(days=10)),
        ],
        profile,
        production=False,
        query_cutoff=CURRENT_SESSION,
    )
    assert leaked["candidate_count"] == control["candidate_count"]
    assert leaked["normalization"] == control["normalization"]
    assert leaked["statistics"] == control["statistics"]
    assert leaked["analog_quality"] == control["analog_quality"]
    assert {match["snapshot_id"] for match in leaked["matches"]} == {
        match["snapshot_id"] for match in control["matches"]
    }

    # Counter-evidence: the same dimensions and returns are admitted from a past
    # session, so the equality above is not vacuous.
    admitted_row = _candidate(profile, "past", BOUNDARY_SESSION, dimensions_seed=40)
    for horizon in profile.config["horizons"]:
        admitted_row["outcomes"][horizon]["return_ratio"] = 5.0
    admitted = match_snapshot(
        current,
        history + [admitted_row],
        profile,
        production=False,
        query_cutoff=CURRENT_SESSION,
    )
    assert admitted["candidate_count"] == control["candidate_count"] + 1
    assert (
        admitted["statistics"]["1"]["baseline_probability"]
        != control["statistics"]["1"]["baseline_probability"]
    )
    assert "snap-past" in {match["snapshot_id"] for match in admitted["matches"]}
