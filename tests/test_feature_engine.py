from datetime import datetime
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import src.engine.feature_engine as fe


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

    def get(self):
        return self

    def table(self, name):
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
    monkeypatch.setattr(fe, 'SupabaseClient', lambda: db)

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
    monkeypatch.setattr(fe, 'SupabaseClient', lambda: db)
    monkeypatch.setattr(fe, 'datetime', _FixedDatetime)

    upserted = fe.calculate_features_for_symbol_incremental('SSI', timeframes=['1m'], warmup_bars=2)
    assert upserted == 2
    recs = db.upsert_calls[0][1]
    assert all(r['time'].startswith('2026-05-26T17:0') for r in recs)


def test_no_rows_returns_zero(monkeypatch):
    db = _DB([])
    monkeypatch.setattr(fe, 'SupabaseClient', lambda: db)
    assert fe.calculate_features_for_symbol_full_chunked('SSI', timeframes=['1m']) == 0
    assert fe.calculate_features_for_symbol_incremental('SSI', timeframes=['1m']) == 0


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


def test_full_mode_derives_higher_timeframe_features_without_writing_stock_intraday(monkeypatch):
    rows = []
    base = pd.Timestamp('2026-05-20T02:00:00Z')
    for i in range(10):
        rows.append(_mk_row((base + pd.Timedelta(minutes=i)).strftime('%Y-%m-%dT%H:%M:%SZ'), i))

    db = _DB(rows)
    monkeypatch.setattr(fe, 'SupabaseClient', lambda: db)

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


def test_return_from_prev_close_falls_back_to_previous_intraday_session():
    rows = [
        _mk_row('2026-05-19T02:00:00Z', 0),
        _mk_row('2026-05-19T02:01:00Z', 1),
        _mk_row('2026-05-20T02:00:00Z', 10),
    ]

    feats = fe.compute_feature_dataframe(pd.DataFrame(rows))

    assert feats.iloc[2]['return_from_prev_close'] == ((20.5 / 11.5) - 1)


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
