import math

from src.screener.rules import VERSION, evaluate


GOOD = {
    "close": 110, "ema20": 100, "ema50": 95, "rsi14": 55,
    "macd_histogram": 0.01, "volume_ratio": 1.5, "value_ratio": 1,
}


def test_v1_valid_pass():
    result = evaluate(GOOD)
    assert VERSION == "v1"
    assert result["status"] == "PASS"
    assert result["score"] == 100
    assert all(result["rule_results"]["conditions"].values())


def test_complete_but_weak_is_fail_not_missing():
    result = evaluate({**GOOD, "rsi14": 71, "volume_ratio": 0.8})
    assert result["status"] == "FAIL"
    assert result["score"] == 60
    assert result["missing_fields"] == []


def test_missing_input_is_not_evaluable_never_zero():
    result = evaluate({**GOOD, "value_ratio": None})
    assert result["status"] == "NOT_EVALUABLE"
    assert result["score"] is None
    assert result["rule_results"]["conditions"]["value"] is None
    assert result["missing_fields"] == ["value_ratio"]


def test_no_row_is_not_evaluable():
    assert evaluate(None)["status"] == "NOT_EVALUABLE"


def test_nan_infinity_and_out_of_range_are_invalid():
    for field, value in (("macd_histogram", math.nan),
                         ("ema20", math.inf), ("rsi14", 120),
                         ("volume_ratio", -1), ("close", 0)):
        assert field in evaluate({**GOOD, field: value})["missing_fields"]


def test_boundaries_are_explicit():
    assert evaluate({**GOOD, "rsi14": 50, "volume_ratio": 1, "value_ratio": 1})["status"] == "PASS"
    assert evaluate({**GOOD, "rsi14": 70})["status"] == "PASS"
    assert evaluate({**GOOD, "macd_histogram": 0})["status"] == "FAIL"
