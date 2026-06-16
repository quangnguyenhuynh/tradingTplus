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
            rows = [r for r in rows if r['time'] >= self._gte]
        if self._lt is not None:
            rows = [r for r in rows if r['time'] < self._lt]
        rows = sorted(rows, key=lambda r: r['time'], reverse=self._desc)
        return _Result(rows[self._start:self._end + 1])


class _DB:
    def __init__(self, rows):
        self.rows = rows
        self.upsert_calls = []

    def get(self):
        return self

    def table(self, _name):
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
