from datetime import datetime
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import src.features.runner as fe
import src.features.common as fc
import src.features.daily as daily_flow
import src.features.intraday as intraday_flow
import src.features.runtime as feature_runtime


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows):
        self.rows = rows
        self._gte = None
        self._lt = None
        self._lte = None
        self._desc = False
        self._start = 0
        self._end = 999

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def gte(self, _col, val):
        self._gte = val
        return self

    def lt(self, _col, val):
        self._lt = val
        return self

    def lte(self, _col, val):
        self._lte = val
        return self

    def order(self, _col, desc=False):
        self._desc = desc
        return self

    def range(self, start, end):
        self._start = start
        self._end = end
        return self

    def execute(self):
        rows = list(self.rows)
        if self._gte is not None:
            rows = [r for r in rows if r.get('time', r.get('trading_date')) >= self._gte]
        if self._lt is not None:
            rows = [r for r in rows if r.get('time', r.get('trading_date')) < self._lt]
        if self._lte is not None:
            rows = [r for r in rows if r.get('time', r.get('trading_date')) <= self._lte]
        sort_key = 'time' if rows and 'time' in rows[0] else 'trading_date'
        rows = sorted(rows, key=lambda r: r[sort_key], reverse=self._desc) if rows else rows
        return _Result(rows[self._start:self._end + 1])


class _DB:
    def __init__(self, rows, daily_rows=None):
        self.rows = rows
        self.daily_rows = daily_rows or []
        self.upsert_calls = []
        self.table_calls = []

    def get(self):
        return self

    def table(self, name):
        self.table_calls.append(name)
        if name == 'stock_daily':
            return _Query(self.daily_rows)
        return _Query(self.rows)

    def _with_retry(self, action, action_name=None):
        return action()

    def _upsert_in_batches(self, table_name, records, on_conflict=None, batch_size=1000):
        self.upsert_calls.append((table_name, records, on_conflict, batch_size))


def _mk_row(ts: str, i: int):
    return {
        'time': ts,
        'open': 10 + i,
        'high': 11 + i,
        'low': 9 + i,
        'close': 10.5 + i,
        'volume': 100 + i,
        'value': 1000 + i,
    }


def test_full_mode_paginates_over_1000_rows(monkeypatch):
    rows = []
    base = pd.Timestamp('2026-05-20T02:00:00Z')
    for i in range(1205):
        rows.append(_mk_row((base + pd.Timedelta(minutes=i)).strftime('%Y-%m-%dT%H:%M:%SZ'), i))

    db = _DB(rows)
    monkeypatch.setattr(intraday_flow, 'SupabaseClient', lambda: db)

    upserted = fe.calculate_features_for_symbol_full_chunked('SSI', timeframes=['1m'])
    assert upserted == 1205
    assert len(db.upsert_calls) == 1
    assert len(db.upsert_calls[0][1]) == 1205


def test_incremental_mode_uses_today_and_warmup(monkeypatch):
    warmup = [_mk_row('2026-05-26T16:00:00Z', 1), _mk_row('2026-05-26T16:01:00Z', 2)]
    today = [_mk_row('2026-05-26T17:01:00Z', 3), _mk_row('2026-05-26T17:02:00Z', 4)]  # 00:01/00:02 VN
    rows = warmup + today

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            t = pd.Timestamp('2026-05-27T03:00:00+07:00').to_pydatetime()
            return t if tz is None else t.astimezone(tz)

    db = _DB(rows)
    monkeypatch.setattr(intraday_flow, 'SupabaseClient', lambda: db)
    monkeypatch.setattr(feature_runtime, 'datetime', _FixedDatetime)

    upserted = fe.calculate_features_for_symbol_incremental('SSI', timeframes=['1m'], warmup_bars=2)
    assert upserted == 2
    recs = db.upsert_calls[0][1]
    assert all(r['time'].startswith('2026-05-26T17:0') for r in recs)


def test_no_rows_returns_zero(monkeypatch):
    db = _DB([])
    monkeypatch.setattr(intraday_flow, 'SupabaseClient', lambda: db)
    assert fe.calculate_features_for_symbol_full_chunked('SSI', timeframes=['1m']) == 0
    assert fe.calculate_features_for_symbol_incremental('SSI', timeframes=['1m']) == 0


def test_daily_execution_reads_only_stock_daily(monkeypatch):
    db = _DB([], daily_rows=[_mk_daily("2026-05-20", 1)])
    monkeypatch.setattr(daily_flow, "SupabaseClient", lambda: db)

    count = daily_flow.calculate_daily_features_for_symbol(
        "SSI",
        mode="full",
    )

    assert count == 1
    assert db.table_calls == ["stock_daily"]
    assert [call[0] for call in db.upsert_calls] == ["features"]


def test_timestamp_conversion_utc_in_records():
    df = pd.DataFrame([_mk_row('2026-05-26T17:01:00Z', 1)])
    feats = fe.compute_feature_dataframe(df)
    recs = fe._build_feature_records(feats, 'SSI', '1m')
    assert recs[0]['time'].endswith('Z')


def test_aggregate_timeframe_builds_5m_bars_from_1m_source():
    rows = []
    base = pd.Timestamp('2026-05-20T02:00:00Z')
    for i in range(7):
        rows.append(_mk_row((base + pd.Timedelta(minutes=i)).strftime('%Y-%m-%dT%H:%M:%SZ'), i))

    agg = fe.aggregate_timeframe(pd.DataFrame(rows), '5m')

    assert len(agg) == 2
    assert agg.iloc[0]['open'] == 10
    assert agg.iloc[0]['high'] == 15
    assert agg.iloc[0]['low'] == 9
    assert agg.iloc[0]['close'] == 14.5
    assert agg.iloc[0]['volume'] == sum(100 + i for i in range(5))
    assert agg.iloc[0]['value'] == sum(1000 + i for i in range(5))


def test_aggregate_partial_5m_bucket_sums_only_observed_candles():
    base = pd.Timestamp('2026-05-20T02:00:00Z')
    rows = [
        _mk_row((base + pd.Timedelta(minutes=i)).strftime('%Y-%m-%dT%H:%M:%SZ'), i)
        for i in [0, 1, 3, 4, 10]
    ]

    agg = fe.aggregate_timeframe(pd.DataFrame(rows), '5m')

    assert len(agg) == 2  # The entirely empty 09:05 bucket is not fabricated.
    assert agg.iloc[0]['close'] == 14.5
    assert agg.iloc[0]['volume'] == sum(100 + i for i in [0, 1, 3, 4])
    assert agg.iloc[0]['value'] == sum(1000 + i for i in [0, 1, 3, 4])
    assert agg.iloc[1]['time'] == pd.Timestamp('2026-05-20T02:10:00Z')


def test_aggregation_does_not_cross_lunch_break():
    rows = [_mk_row('2026-05-20T04:29:00Z', 0), _mk_row('2026-05-20T06:00:00Z', 1)]

    agg = fe.aggregate_timeframe(pd.DataFrame(rows), '60m')

    assert len(agg) == 2
    assert list(agg['volume']) == [100, 101]


def test_full_mode_derives_higher_timeframe_features_without_writing_stock_intraday(monkeypatch):
    rows = []
    base = pd.Timestamp('2026-05-20T02:00:00Z')
    for i in range(10):
        rows.append(_mk_row((base + pd.Timedelta(minutes=i)).strftime('%Y-%m-%dT%H:%M:%SZ'), i))

    db = _DB(rows)
    monkeypatch.setattr(intraday_flow, 'SupabaseClient', lambda: db)

    upserted = fe.calculate_features_for_symbol_full_chunked('SSI', timeframes=['1m', '5m'])

    assert upserted == 12
    assert [call[0] for call in db.upsert_calls] == ['features', 'features']
    assert {call[2] for call in db.upsert_calls} == {'symbol,timeframe,time'}
    assert {record['timeframe'] for _, records, _, _ in db.upsert_calls for record in records} == {'1m', '5m'}


def test_feature_engine_falls_back_to_close_times_volume_when_value_null():
    df = pd.DataFrame([
        _mk_row('2026-05-26T17:01:00Z', 1),
        _mk_row('2026-05-26T17:02:00Z', 2),
    ])
    df.loc[0, 'value'] = None
    df.loc[1, 'value'] = 7777

    agg = fe.aggregate_timeframe(df, '1m')
    feats = fe.compute_feature_dataframe(df)

    assert agg.iloc[0]['value'] == 1162
    assert agg.iloc[1]['value'] == 7777
    assert feats.iloc[0]['value'] == 1162
    assert feats.iloc[1]['value'] == 7777


def test_compute_feature_dataframe_phase1_columns_and_no_legacy_columns():
    rows = [_mk_row((pd.Timestamp('2026-05-20T02:00:00Z') + pd.Timedelta(minutes=i)).strftime('%Y-%m-%dT%H:%M:%SZ'), i) for i in range(30)]
    feats = fe.compute_feature_dataframe(pd.DataFrame(rows))

    assert set(fe.FEATURE_COLUMNS).issubset(feats.columns)
    assert {'rsi', 'atr', 'ema_20', 'ema_50', 'vwap', 'bb_upper', 'bb_lower', 'volume_spike'}.isdisjoint(fe.FEATURE_COLUMNS)
    assert {'rsi', 'atr', 'ema_20', 'ema_50', 'vwap', 'bb_upper', 'bb_lower', 'volume_spike'}.isdisjoint(feats.columns)


def test_return_from_prev_close_prefers_stock_daily_previous_close():
    rows = [
        _mk_row('2026-05-19T02:00:00Z', 0),
        _mk_row('2026-05-20T02:00:00Z', 10),
    ]
    daily = pd.DataFrame([
        {'trading_date': '2026-05-19', 'close_price': 99},
        {'trading_date': '2026-05-20', 'close_price': 120},
    ])

    feats = fe.compute_feature_dataframe(pd.DataFrame(rows), daily_df=daily)

    assert feats.iloc[1]['return_from_prev_close'] == ((20.5 / 99) - 1)


def test_return_from_prev_close_without_stock_daily_is_null():
    rows = [
        _mk_row('2026-05-19T02:00:00Z', 0),
        _mk_row('2026-05-19T02:01:00Z', 1),
        _mk_row('2026-05-20T02:00:00Z', 10),
    ]

    feats = fe.compute_feature_dataframe(pd.DataFrame(rows))

    assert pd.isna(feats.iloc[2]['return_from_prev_close'])


def test_aggregate_timeframe_does_not_cross_vietnam_trading_date_boundary():
    rows = [
        _mk_row('2026-05-20T16:58:00Z', 0),  # 2026-05-20 23:58 VN
        _mk_row('2026-05-20T16:59:00Z', 1),
        _mk_row('2026-05-20T17:00:00Z', 2),  # 2026-05-21 00:00 VN
        _mk_row('2026-05-20T17:01:00Z', 3),
    ]

    agg = fe.aggregate_timeframe(pd.DataFrame(rows), '5m')

    assert len(agg) == 2
    assert agg.iloc[0]['time'] == pd.Timestamp('2026-05-20T16:55:00Z')
    assert agg.iloc[0]['close'] == 11.5
    assert agg.iloc[1]['time'] == pd.Timestamp('2026-05-20T17:00:00Z')
    assert agg.iloc[1]['close'] == 13.5


def _mk_daily(date: str, i: int):
    return {
        'trading_date': date,
        'open_price': 100 + i,
        'highest_price': 110 + i,
        'lowest_price': 90 + i,
        'close_price': 105 + i,
        'total_traded_vol': 1000 + i,
        'total_traded_value': 10000 + i,
    }


def test_daily_features_are_computed_from_stock_daily_and_vwap_is_null():
    daily = pd.DataFrame([_mk_daily(f'2026-05-{day:02d}', day) for day in range(1, 25)])

    feats = fe.compute_daily_features(daily)

    assert len(feats) == 24
    assert feats.iloc[-1]['open'] == 124
    assert feats.iloc[-1]['volume_ma20'] == sum(1000 + day for day in range(5, 25)) / 20
    assert pd.isna(feats.iloc[-1]['vwap_intraday'])
    assert pd.isna(feats.iloc[-1]['return_1m'])


def test_daily_breakout_uses_previous_20_bars_without_lookahead():
    rows = [_mk_daily(f'2026-05-{day:02d}', day) for day in range(1, 22)]
    rows[-1]['highest_price'] = 999
    rows[-1]['close_price'] = 200

    feats = fe.compute_daily_features(pd.DataFrame(rows))

    assert feats.iloc[-1]['high_20_bars'] == max(110 + day for day in range(1, 21))
    assert bool(feats.iloc[-1]['close_above_high_20']) is True


def test_intraday_vwap_resets_daily_and_volume_ma20_uses_prior_same_bucket_dates():
    rows = []
    for day in pd.date_range('2026-04-01', periods=21, freq='D'):
        rows.append(_mk_row(day.strftime('%Y-%m-%dT02:00:00Z'), day.day))

    feats = fe.compute_intraday_features(pd.DataFrame(rows), timeframe='1m')

    assert pd.isna(feats.iloc[19]['volume_ma20'])
    assert feats.iloc[20]['volume_ma20'] == pytest.approx(feats.iloc[:20]['volume'].mean())
    assert feats.iloc[20]['vwap_intraday'] == feats.iloc[20]['value'] / feats.iloc[20]['volume']


def test_return_columns_match_timeframe_semantics():
    rows = [_mk_row((pd.Timestamp('2026-05-20T02:00:00Z') + pd.Timedelta(minutes=i)).strftime('%Y-%m-%dT%H:%M:%SZ'), i) for i in range(20)]

    feats_5m = fe.compute_intraday_features(fe.aggregate_timeframe(pd.DataFrame(rows), '5m'), timeframe='5m')
    feats_15m = fe.compute_intraday_features(fe.aggregate_timeframe(pd.DataFrame(rows), '15m'), timeframe='15m')
    feats_60m = fe.compute_intraday_features(fe.aggregate_timeframe(pd.DataFrame(rows), '60m'), timeframe='60m')

    assert feats_5m['return_1m'].isna().all()
    assert feats_5m['return_5m'].notna().any()
    assert feats_15m['return_1m'].isna().all() and feats_15m['return_5m'].isna().all()
    assert feats_60m[['return_1m', 'return_5m', 'return_15m']].isna().all().all()


def _feature_at(feats, timestamp):
    return feats.loc[feats['time'] == pd.Timestamp(timestamp)].iloc[0]


def test_time_aware_returns_match_continuous_wall_clock_horizons():
    base = pd.Timestamp('2026-05-20T02:00:00Z')
    rows = [_mk_row((base + pd.Timedelta(minutes=i)).isoformat(), i) for i in range(16)]

    result = fe.compute_intraday_features(pd.DataFrame(rows), '1m').iloc[-1]

    assert result['return_1m'] == pytest.approx(25.5 / 24.5 - 1)
    assert result['return_5m'] == pytest.approx(25.5 / 20.5 - 1)
    assert result['return_15m'] == pytest.approx(25.5 / 10.5 - 1)


def test_time_aware_return_uses_latest_reference_at_or_before_target():
    times = ['09:43', '09:44', '09:45', '09:46', '09:48', '09:49']
    rows = [_mk_row(f'2026-05-20T{hour}:00+07:00', i) for i, hour in enumerate(times)]

    feats = fe.compute_intraday_features(pd.DataFrame(rows), '1m')
    result = _feature_at(feats, '2026-05-20T02:49:00Z')

    assert result['return_1m'] == pytest.approx(15.5 / 14.5 - 1)
    assert result['return_5m'] == pytest.approx(15.5 / 11.5 - 1)  # exact 09:44 target


def test_time_aware_return_accepts_prior_reference_within_tolerance():
    rows = [
        _mk_row('2026-05-20T02:43:00Z', 0),
        _mk_row('2026-05-20T02:49:00Z', 1),
    ]

    result = fe.compute_intraday_features(pd.DataFrame(rows), '1m').iloc[-1]

    assert result['return_5m'] == pytest.approx(11.5 / 10.5 - 1)


def test_time_aware_return_rejects_stale_or_future_reference():
    rows = [
        _mk_row('2026-05-20T02:41:00Z', 0),  # too old for 09:49 - 5m target
        _mk_row('2026-05-20T02:45:00Z', 1),  # after target; must not be used
        _mk_row('2026-05-20T02:49:00Z', 2),
    ]

    result = fe.compute_intraday_features(pd.DataFrame(rows), '1m').iloc[-1]

    assert pd.isna(result['return_5m'])


def test_time_aware_return_does_not_cross_lunch_or_trading_date():
    rows = [
        _mk_row('2026-05-20T04:29:00Z', 0),
        _mk_row('2026-05-20T06:00:00Z', 1),
        _mk_row('2026-05-21T02:00:00Z', 2),
    ]

    feats = fe.compute_intraday_features(pd.DataFrame(rows), '1m')

    assert pd.isna(feats.iloc[1]['return_15m'])
    assert pd.isna(feats.iloc[2]['return_15m'])


def test_higher_timeframe_returns_use_timestamps():
    rows_5m = [_mk_row(f'2026-05-20T02:{minute:02d}:00Z', i) for i, minute in enumerate([0, 5, 10, 15])]
    rows_15m = [_mk_row(f'2026-05-20T02:{minute:02d}:00Z', i) for i, minute in enumerate([0, 15])]

    features_5m = fe.compute_intraday_features(pd.DataFrame(rows_5m), '5m')
    features_15m = fe.compute_intraday_features(pd.DataFrame(rows_15m), '15m')

    assert features_5m.iloc[-1]['return_5m'] == pytest.approx(13.5 / 12.5 - 1)
    assert features_5m.iloc[-1]['return_15m'] == pytest.approx(13.5 / 10.5 - 1)
    assert features_15m.iloc[-1]['return_15m'] == pytest.approx(11.5 / 10.5 - 1)


def test_bar_based_indicators_match_continuous_input_regression():
    rows = [_mk_row((pd.Timestamp('2026-05-20T02:00:00Z') + pd.Timedelta(minutes=i)).isoformat(), i) for i in range(60)]
    prices = pd.Series([row['close'] for row in rows], dtype='float64')

    feats = fe.compute_intraday_features(pd.DataFrame(rows), '1m')
    expected_macd, expected_signal, expected_histogram = fc.calculate_macd(prices)

    assert feats['rsi14'].equals(fc.calculate_rsi(prices))
    assert feats['ema20'].equals(prices.ewm(span=20, adjust=False, min_periods=20).mean())
    assert feats['macd'].equals(expected_macd)
    assert feats['macd_signal'].equals(expected_signal)
    assert feats['macd_histogram'].equals(expected_histogram)


def test_full_and_incremental_calculation_rules_match_on_overlap():
    base = pd.Timestamp('2026-05-20T02:00:00Z')
    rows = [_mk_row((base + pd.Timedelta(minutes=i)).isoformat(), i) for i in range(60) if i != 43]
    full = fe.compute_intraday_features(pd.DataFrame(rows), '1m')
    incremental_input = pd.DataFrame(rows[-40:])
    incremental = fe.compute_intraday_features(incremental_input, '1m')

    # Incremental mode supplies warm-up rows; compare after the longest return
    # horizon has elapsed within this isolated calculator fixture.
    incremental = incremental.iloc[15:].reset_index(drop=True)
    overlap = full[full['time'].isin(incremental['time'])].reset_index(drop=True)

    pd.testing.assert_series_equal(overlap['return_1m'], incremental['return_1m'], check_names=False)
    pd.testing.assert_series_equal(overlap['return_5m'], incremental['return_5m'], check_names=False)
    pd.testing.assert_series_equal(overlap['return_15m'], incremental['return_15m'], check_names=False)
