from src.strategies.registry import get_strategy, list_strategies


def row(**changes):
    value = {"symbol": "SSI", "timeframe": "1d", "time": "2026-07-01T07:00:00Z", "close_above_high_20": True, "volume_ratio": 1.3}
    value.update(changes)
    return value


def test_registry_and_immutable_config():
    assert [s.strategy_code for s in list_strategies()] == ["BREAKOUT_V1", "PULLBACK_V1"]
    strategy = get_strategy("breakout_v1")
    assert strategy.version == 1
    try:
        strategy.config["x"] = 1
        assert False
    except TypeError:
        pass


def test_daily_pass_fail_not_evaluable():
    strategy = get_strategy("BREAKOUT_V1")
    assert strategy.daily_setup(row()).status == "passed"
    assert strategy.daily_setup(row(close_above_high_20=False)).status == "failed"
    assert strategy.daily_setup(row(volume_ratio=None)).status == "not_evaluable"


def test_intraday_pass_fail_not_evaluable():
    strategy = get_strategy("BREAKOUT_V1")
    base = {"symbol": "SSI", "time": "2026-07-02T02:30:00Z", "close_above_vwap": True, "rsi14": 55}
    rows = {tf: {**base, "timeframe": tf} for tf in ("15m", "60m")}
    assert strategy.intraday_confirm({}, rows, "09:30").status == "passed"
    rows["15m"] = {**rows["15m"], "rsi14": 40}
    assert strategy.intraday_confirm({}, rows, "09:30").status == "failed"
    assert strategy.intraday_confirm({}, {"15m": rows["15m"]}, "09:30").status == "not_evaluable"
