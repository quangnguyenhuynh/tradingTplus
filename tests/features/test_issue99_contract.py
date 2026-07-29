import ast
from pathlib import Path

import pandas as pd
import pytest

from src.features.common import FEATURE_COLUMNS, calculate_macd, calculate_rsi, nullable_comparison
from src.features.intraday import compute_intraday_features, filter_closed_buckets


def _row(time, close=10.0, volume=100):
    return {'time': time, 'open': close - .1, 'high': close + .2, 'low': close - .2,
            'close': close, 'volume': volume, 'value': close * volume}


def test_nullable_comparison_preserves_unknown():
    result = nullable_comparison(pd.Series([2.0, 1.0, None]), pd.Series([1.0, 2.0, 1.0]), lambda a, b: a > b)
    assert result.tolist() == [True, False, pd.NA]


def test_intraday_return_from_open_uses_official_daily_open_and_missing_is_null():
    rows = pd.DataFrame([_row('2026-05-20T02:00:00Z', 12.0)])
    daily = pd.DataFrame([{'trading_date': '2026-05-20', 'open_price': 10.0, 'close_price': 9.0}])
    assert compute_intraday_features(rows, '1m', daily).iloc[0]['return_from_open'] == pytest.approx(.2)
    assert pd.isna(compute_intraday_features(rows, '1m').iloc[0]['return_from_open'])


def test_closed_filter_keeps_session_ending_short_bucket():
    frame = pd.DataFrame([_row('2026-05-20T04:00:00Z')])  # 11:00 VN: short bucket closes 11:30
    cutoff = pd.Timestamp('2026-05-20T11:30:00+07:00')
    result = filter_closed_buckets(frame, '60m', cutoff)
    assert result['time'].tolist() == ['2026-05-20T04:00:00Z']


def test_indicator_reference_constants_are_independent_regression_values():
    # Constants were independently generated with a spreadsheet implementing
    # adjust=False EMA/Wilder recurrences, not by calling project functions.
    prices = pd.Series([1., 2., 3., 4., 5., 6., 7., 8., 9., 10., 9., 8., 9., 10., 11., 12., 13., 12., 11., 10., 12., 14., 13., 15., 16., 15., 17., 18., 16., 19., 20., 18., 21., 22., 20., 23., 24., 22., 25., 26.])
    rsi = calculate_rsi(prices)
    macd, signal, histogram = calculate_macd(prices)
    assert rsi.iloc[-1] == pytest.approx(70.56109043973443, abs=1e-9)
    assert macd.iloc[-1] == pytest.approx(3.902402355062467, abs=1e-9)
    assert signal.iloc[-1] == pytest.approx(3.5813062247408864, abs=1e-9)
    assert histogram.iloc[-1] == pytest.approx(.32109613032158046, abs=1e-9)
    assert rsi.iloc[:13].isna().all()
    assert signal.iloc[:33].isna().all()


def test_migration_and_schema_contract():
    migration = Path('migrations/20260729_drop_legacy_feature_columns.sql').read_text()
    schema = Path('schema.sql').read_text()
    for legacy in ('rsi', 'atr', 'ema_20', 'ema_50', 'vwap', 'bb_upper', 'bb_lower', 'volume_spike'):
        assert f'DROP COLUMN IF EXISTS {legacy}' in migration
    assert not any(line.strip().upper().endswith(' CASCADE;') for line in migration.splitlines())
    feature_block = schema.split('CREATE TABLE IF NOT EXISTS "public"."features"', 1)[1].split(');', 1)[0]
    for column in FEATURE_COLUMNS:
        assert f'"{column}"' in feature_block


def test_feature_package_has_source_owners_without_legacy_engine_shims():
    assert not Path("src/engine/feature_calculator.py").exists()
    assert not Path("src/engine/feature_engine.py").exists()

    daily_source = Path("src/features/daily.py").read_text()
    intraday_source = Path("src/features/intraday.py").read_text()
    runner_source = Path("src/features/runner.py").read_text()

    assert "def compute_daily_features(" in daily_source
    assert "def calculate_daily_features_for_symbol(" in daily_source
    assert "def compute_intraday_features(" in intraday_source
    assert "def calculate_intraday_features_for_symbol(" in intraday_source

    runner_tree = ast.parse(runner_source)
    function_names = [
        node.name
        for node in runner_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert len(function_names) == len(set(function_names))
    assert "def _fetch_stock_intraday_paginated(" not in runner_source
    assert "def _fetch_stock_daily_rows(" not in runner_source
