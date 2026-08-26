import numpy as np
import pandas as pd
import pytest

from src.index_features.calculator import compute_index_daily_features


def source_rows(count=80):
    dates = pd.bdate_range("2026-01-01", periods=count)
    sequence = np.arange(count, dtype=float)
    return pd.DataFrame({
        "index_code": "VNINDEX", "trading_date": dates,
        "index_value": 100 + sequence, "total_vol": 1000 + sequence,
        "total_val": 10000 + sequence, "total_match_vol": 800 + sequence,
        "total_match_val": 8000 + sequence, "total_deal_vol": 200.0,
        "total_deal_val": 2000.0, "advances": 60.0, "no_changes": 10.0,
        "declines": 30.0, "ceilings": 5.0, "floors": 2.0,
    })


def test_price_rolling_and_momentum_formulas():
    result = compute_index_daily_features(source_rows())
    row = result.iloc[-1]
    values = source_rows()["index_value"]
    for lag in (1, 3, 5, 10):
        assert row[f"index_return_{lag}d"] == pytest.approx(values.iloc[-1] / values.iloc[-1-lag] - 1)
    assert row["index_ma20"] == pytest.approx(values.iloc[-20:].mean())
    assert row["index_ma50"] == pytest.approx(values.iloc[-50:].mean())
    assert row["index_rsi14"] == pytest.approx(100.0)
    returns = values.pct_change()
    assert row["index_volatility_20d"] == pytest.approx(returns.iloc[-20:].std())
    assert row["index_drawdown_20d"] == pytest.approx(0.0)
    assert row["index_drawdown_60d"] == pytest.approx(0.0)
    assert row["index_macd"] == pytest.approx(values.ewm(span=12, adjust=False, min_periods=12).mean().iloc[-1] - values.ewm(span=26, adjust=False, min_periods=26).mean().iloc[-1])
    assert row["index_macd_histogram"] == pytest.approx(row["index_macd"] - row["index_macd_signal"])


def test_breadth_and_liquidity_formulas():
    row = compute_index_daily_features(source_rows()).iloc[-1]
    assert row["breadth_total"] == 100
    assert row["index_breadth_net"] == 30
    assert row["index_breadth_ratio"] == pytest.approx(.3)
    assert row["index_advance_pct"] == pytest.approx(.6)
    assert row["index_decline_pct"] == pytest.approx(.3)
    assert row["index_unchanged_pct"] == pytest.approx(.1)
    assert row["index_ceiling_pct"] == pytest.approx(.05)
    assert row["index_floor_pct"] == pytest.approx(.02)
    assert row["index_limit_balance"] == pytest.approx(.03)
    assert row["index_breadth_ma5"] == pytest.approx(.3)
    assert row["index_breadth_ma10"] == pytest.approx(.3)
    assert row["index_match_vol_ratio"] == pytest.approx(879 / 1079)
    assert row["index_deal_val_ratio"] == pytest.approx(2000 / 10079)


def test_null_zero_denominator_and_insufficient_history_are_null():
    rows = source_rows(10)
    rows.loc[9, ["total_vol", "total_val", "advances"]] = [0, 0, np.nan]
    result = compute_index_daily_features(rows)
    row = result.iloc[-1]
    assert pd.isna(row["breadth_total"])
    assert pd.isna(row["index_breadth_ratio"])
    assert pd.isna(row["index_match_vol_ratio"])
    assert pd.isna(row["index_match_val_ratio"])
    assert pd.isna(row["index_ma20"])
    assert pd.isna(row["index_ma50"])
    assert pd.isna(row["index_drawdown_60d"])
    assert not np.isinf(result.select_dtypes("number").to_numpy()).any()


def test_no_synthetic_weekend_rows_or_future_leakage():
    rows = source_rows(20)
    first = compute_index_daily_features(rows).iloc[10]["index_return_1d"]
    mutated = rows.copy(); mutated.loc[19, "index_value"] = 999999
    second = compute_index_daily_features(mutated).iloc[10]["index_return_1d"]
    assert first == second
    assert set(compute_index_daily_features(rows)["trading_date"]) == set(rows["trading_date"])
