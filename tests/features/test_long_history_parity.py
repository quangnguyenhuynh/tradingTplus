"""Deterministic Phase 0 full-versus-bounded-warm-up parity evidence."""

import math

import pandas as pd
import pytest

from src.features.common import FEATURE_COLUMNS
from src.features.daily import compute_daily_features
from src.features.intraday import aggregate_timeframe, compute_intraday_features
from src.features.runtime import build_feature_records


AUDIT_COLUMNS = {"last_updated_at"}
FLOAT_ABS_TOLERANCE = 1e-6
FLOAT_REL_TOLERANCE = 1e-9


def _daily_fixture(count=1501):
    rows = []
    for i, stamp in enumerate(pd.bdate_range("2019-01-02", periods=count)):
        trend = 40 + i * 0.013
        wave = math.sin(i / 11) * 1.7 + math.cos(i / 37) * 0.9
        open_price = trend + wave
        close = open_price + math.sin(i / 5) * 0.8
        rows.append({
            "trading_date": stamp.date().isoformat(),
            "open_price": open_price,
            "highest_price": max(open_price, close) + 0.4 + (i % 7) * 0.01,
            "lowest_price": min(open_price, close) - 0.3 - (i % 5) * 0.01,
            "close_price": close,
            "total_traded_vol": 100_000 + (i * 7919) % 900_000,
            "total_traded_value": 5_000_000 + (i * 104729) % 40_000_000,
        })
    return rows


def _intraday_fixture(session_count=251):
    rows, daily = [], []
    for day_index, stamp in enumerate(pd.bdate_range("2025-01-02", periods=session_count)):
        daily_open = 70 + day_index * 0.021 + math.sin(day_index / 9)
        daily.append({
            "trading_date": stamp.date().isoformat(), "open_price": daily_open,
            "close_price": daily_open + math.sin(day_index / 7) * 0.3,
        })
        local = pd.Timestamp(stamp.date(), tz="Asia/Ho_Chi_Minh")
        minutes = [local.replace(hour=9) + pd.Timedelta(minutes=i) for i in range(30)]
        minutes += [local.replace(hour=13) + pd.Timedelta(minutes=i) for i in range(30)]
        for minute_index, minute in enumerate(minutes):
            sequence = day_index * 60 + minute_index
            open_price = daily_open + math.sin(sequence / 13) * 0.6
            close = open_price + math.cos(sequence / 17) * 0.15
            volume = 500 + (sequence * 97) % 4_000
            rows.append({
                "time": minute.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                "open": open_price,
                "high": max(open_price, close) + 0.08,
                "low": min(open_price, close) - 0.07,
                "close": close,
                "volume": volume,
                "value": round(close * volume),
            })
    return rows, daily


def _records(frame, timeframe):
    return [
        {key: value for key, value in row.items() if key not in AUDIT_COLUMNS}
        for row in build_feature_records(frame, "SSI", timeframe)
    ]


def _compare_all_columns(expected, actual):
    assert len(expected) == len(actual)
    assert set(expected[0]) == {"symbol", "timeframe", "time", *FEATURE_COLUMNS}
    maxima = {}
    for wanted, got in zip(expected, actual):
        for column in wanted:
            left, right = wanted[column], got[column]
            if isinstance(left, float) and isinstance(right, float):
                absolute = abs(left - right)
                relative = absolute / max(abs(left), abs(right), 1.0)
                prior = maxima.get(column, (0.0, 0.0))
                maxima[column] = (max(prior[0], absolute), max(prior[1], relative))
                assert absolute <= FLOAT_ABS_TOLERANCE or relative <= FLOAT_REL_TOLERANCE, (
                    column, wanted["time"], left, right, absolute, relative
                )
            else:
                assert left == right, (column, wanted["time"], left, right)
    return maxima


def test_daily_five_year_incremental_matches_full_all_persisted_columns():
    rows = _daily_fixture()
    assert len(rows) > 1500
    assert (pd.Timestamp(rows[-1]["trading_date"]) - pd.Timestamp(rows[0]["trading_date"])).days > 5 * 365
    full = compute_daily_features(pd.DataFrame(rows))
    target_date = pd.Timestamp(rows[-1]["trading_date"])
    warmup_start = (target_date - pd.DateOffset(years=5)).date()
    bounded_rows = [row for row in rows if pd.Timestamp(row["trading_date"]).date() >= warmup_start]
    bounded = compute_daily_features(pd.DataFrame(bounded_rows))
    expected = _records(full.tail(1), "1d")
    actual = _records(bounded.tail(1), "1d")
    maxima = _compare_all_columns(expected, actual)
    assert all(absolute <= FLOAT_ABS_TOLERANCE for absolute, _ in maxima.values()), maxima
    assert len(bounded_rows) < len(rows)
    assert math.ceil(len(bounded_rows) / 1000) < math.ceil(len(rows) / 1000) or len(rows) - len(bounded_rows) > 0


@pytest.mark.parametrize("timeframe", ["15m", "60m"])
def test_intraday_200_and_250_session_parity_against_full(timeframe):
    rows, daily = _intraday_fixture()
    assert len(rows) == 251 * 60
    full_aggregated = aggregate_timeframe(pd.DataFrame(rows), timeframe)
    full = compute_intraday_features(full_aggregated, timeframe, pd.DataFrame(daily))
    target = pd.Timestamp(daily[-1]["trading_date"]).date()
    full_target = full[
        pd.to_datetime(full["time"], utc=True).dt.tz_convert("Asia/Ho_Chi_Minh").dt.date == target
    ]
    expected = _records(full_target, timeframe)

    evidence = {}
    for sessions in (200, 250):
        first = pd.Timestamp(daily[-sessions]["trading_date"]).date()
        bounded_rows = [
            row for row in rows
            if pd.Timestamp(row["time"]).tz_convert("Asia/Ho_Chi_Minh").date() >= first
        ]
        bounded_daily = [row for row in daily if pd.Timestamp(row["trading_date"]).date() >= first]
        aggregated = aggregate_timeframe(pd.DataFrame(bounded_rows), timeframe)
        computed = compute_intraday_features(aggregated, timeframe, pd.DataFrame(bounded_daily))
        selected = computed[
            pd.to_datetime(computed["time"], utc=True).dt.tz_convert("Asia/Ho_Chi_Minh").dt.date == target
        ]
        evidence[sessions] = _compare_all_columns(expected, _records(selected, timeframe))
        assert len(bounded_rows) == sessions * 60
        assert len(bounded_rows) < len(rows)
        assert math.ceil(len(bounded_rows) / 1000) <= math.ceil(sessions * 60 / 1000)

    assert all(
        absolute <= FLOAT_ABS_TOLERANCE
        for absolute, _relative in evidence[250].values()
    ), evidence[250]

