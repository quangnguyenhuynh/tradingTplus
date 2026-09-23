from datetime import date, timedelta
from decimal import Decimal
import random

import pytest

from src.foreign_features.calculator import FORMULA_VERSION, calculate_symbol
from src.foreign_features.validator import decimal_value, validate_source_row


def days(count, start=date(2026, 7, 1), step=1):
    return [(start + timedelta(days=i * step)).isoformat() for i in range(count)]


def row(day, buy, sell, turnover, symbol="SSI"):
    return {
        "symbol": symbol, "trading_date": day,
        "foreign_buy_val_total": buy, "foreign_sell_val_total": sell,
        "net_foreign_val": Decimal(str(buy)) - Decimal(str(sell)),
        "total_traded_value": turnover,
        "foreign_buy_vol_total": buy, "foreign_sell_vol_total": sell,
        "net_foreign_vol": Decimal(str(buy)) - Decimal(str(sell)),
    }


def test_five_rows_hand_calculated_without_calendar_and_twenty_is_insufficient():
    dates = days(5, step=4)
    inputs = [row(d, b, s, v) for d, b, s, v in zip(dates, [100, 0, 30, 0, 20], [0, 50, 10, 0, 0], [1000, 100, 200, 0, 100])]
    out = calculate_symbol(inputs, dates[-1])
    assert out["formula_version"] == FORMULA_VERSION == 2
    assert out["net_value_5d"] == Decimal(90)
    assert out["activity_value_5d"] == Decimal(210)
    assert out["net_value_ratio_5d"] == Decimal(90) / Decimal(1400)
    assert out["activity_ratio_5d"] == Decimal(210) / Decimal(2800)
    assert (out["buy_days_5d"], out["sell_days_5d"]) == (3, 1)
    assert "net_value_20d" not in out
    assert out["quality_status"]["20"]["status"] == "INSUFFICIENT_HISTORY"
    assert out["quality_status"]["window_basis"] == "symbol_rows"


def test_twenty_sparse_calendar_rows_and_non_overlapping_change_are_exact():
    dates = days(20, step=3)  # 20 rows spanning 58 calendar days
    inputs = [row(d, 10**30 + i, 10**30, 10**32) for i, d in enumerate(dates, 1)]
    random.Random(3).shuffle(inputs)
    out = calculate_symbol(inputs, dates[-1])
    assert out["net_value_20d"] == sum(range(1, 21))
    assert out["net_value_ratio_change_5d"] == Decimal(sum(range(16, 21)) - sum(range(11, 16))) / Decimal(5 * 10**32)
    assert out["quality_status"]["change_5d"]["previous"]["dates"] == dates[10:15]
    assert out["quality_status"]["change_5d"]["current"]["dates"] == dates[15:20]


def test_missing_other_symbol_day_is_irrelevant_and_symbols_may_not_mix():
    ssi_dates = days(5, step=2)
    out = calculate_symbol([row(d, 2, 1, 10) for d in ssi_dates], ssi_dates[-1])
    assert out["quality_status"]["5"]["dates"] == ssi_dates
    with pytest.raises(ValueError, match="MIXED_SYMBOL_SOURCE"):
        calculate_symbol([row(ssi_dates[0], 1, 0, 10), row(ssi_dates[1], 1, 0, 10, "HPG")], ssi_dates[1])


def test_duplicate_rejected_and_missing_target_does_not_fall_back():
    dates = days(5)
    inputs = [row(d, 1, 0, 10) for d in dates]
    with pytest.raises(ValueError, match="DUPLICATE_SOURCE"):
        calculate_symbol(inputs + [dict(inputs[-1])], dates[-1])
    assert calculate_symbol(inputs, "2026-07-10") is None


def test_existing_null_row_keeps_position_and_invalidates_only_affected_metrics():
    dates = days(6)
    inputs = [row(d, 2, 1, 10) for d in dates]
    inputs[-2]["foreign_buy_val_total"] = None
    out = calculate_symbol(inputs, dates[-1])
    assert out["quality_status"]["5"]["dates"] == dates[1:]
    assert out.get("activity_value_5d") is None
    assert out["net_value_5d"] == 5
    assert out["quality_status"]["5"]["status"] == "INVALID_SOURCE"


def test_volume_problem_does_not_remove_value_metrics_and_is_fingerprinted():
    dates = days(5)
    inputs = [row(d, 2, 1, 10) for d in dates]
    baseline = calculate_symbol(inputs, dates[-1])
    inputs[-1]["net_foreign_vol"] = 999
    changed = calculate_symbol(inputs, dates[-1])
    assert changed["net_value_5d"] == 5
    assert changed["quality_status"]["5"]["status"] == "PARTIAL"
    assert changed["source_fingerprint"] != baseline["source_fingerprint"]


def test_fingerprint_ignores_rows_outside_twenty_row_window():
    dates = days(21)
    inputs = [row(d, 2, 1, 10) for d in dates]
    original = calculate_symbol(inputs, dates[-1])["source_fingerprint"]
    inputs[0]["foreign_buy_val_total"] = 999
    assert calculate_symbol(inputs, dates[-1])["source_fingerprint"] == original


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), float("-inf"), "x"])
def test_non_finite_boolean_and_invalid_numbers(bad):
    with pytest.raises(ValueError):
        decimal_value(bad)


def test_net_and_volume_mismatch_are_separate():
    source = row("2026-08-01", 10, 2, 100)
    source["net_foreign_val"] = 7
    source["net_foreign_vol"] = 9
    reasons = validate_source_row(source)
    assert "NET_VALUE_MISMATCH" in reasons and "NET_VOLUME_MISMATCH" in reasons
