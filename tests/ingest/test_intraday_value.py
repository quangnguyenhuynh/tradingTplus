import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.intraday_value import calculate_trade_value


def test_calculate_trade_value_returns_bigint_safe_int():
    value = calculate_trade_value("10.5", "100")

    assert value == 1050
    assert type(value) is int


def test_calculate_trade_value_rounds_and_keeps_nulls():
    assert calculate_trade_value("10.25", "3") == 31
    assert calculate_trade_value(None, "3") is None
    assert calculate_trade_value("10.25", None) is None
    assert calculate_trade_value("bad", "3") is None
    assert calculate_trade_value("10.25", "") is None


def test_calculate_trade_value_zero_volume_is_zero_int():
    value = calculate_trade_value("10.5", "0")

    assert value == 0
    assert type(value) is int
