import pytest

import src.features.policy as policy


def _summary(**overrides):
    value = {
        "flow": "features",
        "status": "OK",
        "total_records": 0,
        "records_by_timeframe": {},
        "errors": [],
    }
    value.update(overrides)
    return value


def test_default_persisted_feature_timeframes_are_15m_60m_1d():
    assert policy.DEFAULT_PERSISTED_FEATURE_TIMEFRAMES == ("15m", "60m", "1d")
    assert policy.PERSISTED_INTRADAY_TIMEFRAMES == ("15m", "60m")


@pytest.mark.parametrize("timeframe", ["1m", "5m"])
def test_persistence_policy_rejects_low_timeframes(timeframe):
    with pytest.raises(ValueError, match="do not persist features for 1m or 5m"):
        policy.validate_persisted_timeframes([timeframe])


def test_intraday_policy_rejects_daily():
    with pytest.raises(ValueError, match="features-intraday accepts only"):
        policy.validate_intraday_persisted_timeframes(["1d"])


def test_intraday_public_runner_delegates_only_allowed_timeframes(monkeypatch):
    captured = {}

    def fake_runner(**kwargs):
        captured.update(kwargs)
        return _summary(flow="features-intraday")

    monkeypatch.setattr(policy, "_run_intraday_features", fake_runner)
    result = policy.run_intraday_features_with_summary(
        symbols=["SSI"],
        mode="incremental",
        timeframes=["15m", "60m"],
        target_date="10/07/2026",
        as_of="14:30",
    )

    assert result["status"] == "OK"
    assert captured["timeframes"] == ("15m", "60m")
    assert captured["symbols"] == ["SSI"]
    assert captured["as_of"] == "14:30"


def test_mixed_public_runner_uses_persisted_defaults(monkeypatch):
    captured = {}

    def fake_runner(**kwargs):
        captured.update(kwargs)
        return _summary()

    monkeypatch.setattr(policy, "_run_mixed_features", fake_runner)
    policy.run_feature_engine_with_summary(symbols=["SSI"], mode="full")

    assert captured["timeframes"] == ("15m", "60m", "1d")
