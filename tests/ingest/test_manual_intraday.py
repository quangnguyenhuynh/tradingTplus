"""Offline synthetic safety tests; no live API/database writes."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from src.ingest.stock_intraday.manual import run_manual_intraday, scope, semantic_hash
from src.providers.ssi.adapters.v3 import SSIV3Adapter
from src.providers.ssi.clients.rest_v3 import SSIV3Client


def candle(minute='15', **changes):
    return dict(symbol='SSI', tradingDate=f'2026/10/20 09:{minute}:00',
                open='10', high='11', low='9', close='10', volume='100', value='999999', **changes)


class Response:
    status_code = 200
    def __init__(self, body):
        self.body = body
    def json(self):
        return self.body


class Session:
    def __init__(self, bodies):
        self.bodies = list(bodies)
        self.calls = []
    def request(self, *args, **kwargs):
        self.calls.append(kwargs)
        body = self.bodies.pop(0)
        if isinstance(body, Exception):
            raise body
        return Response(body)


def adapter(rows=None, bodies=None, **options):
    session = Session(bodies if bodies is not None else [{'data': rows or [candle()]}, {'code': 204, 'msg': 'No Content'}])
    client = SSIV3Client(session=session, max_attempts=1)
    client.token = 'offline-test'
    real = SSIV3Adapter(client)
    if options:
        class Bounded:
            def preview_intraday(self, symbol, day, **kwargs):
                return real.preview_intraday(symbol, day, **kwargs, **options)
        return Bounded(), session
    return real, session


class Query:
    def __init__(self, db, table):
        self.db, self.table, self.filters, self.operation = db, table, [], 'read'
        self.bounds = (0, 99999)
    def select(self, *args, **kwargs): return self
    def eq(self, field, value):
        self.filters.append(('eq', field, value)); return self
    def gte(self, field, value):
        self.filters.append(('gte', field, value)); return self
    def lt(self, field, value):
        self.filters.append(('lt', field, value)); return self
    def order(self, *args): return self
    def range(self, first, last): self.bounds = first, last; return self
    def upsert(self, rows, **kwargs):
        assert kwargs['ignore_duplicates'] is True
        assert kwargs['returning'] == 'representation'
        self.operation, self.rows, self.conflict = 'insert', deepcopy(rows), kwargs['on_conflict'].split(',')
        return self
    def execute(self):
        self.db.calls.append((self.table, self.operation, self.filters))
        if self.operation == 'insert':
            self.db.mutations.append((self.table, deepcopy(self.rows)))
            if self.db.hook:
                self.db.hook(self)
            inserted = []
            for row in self.rows:
                if not any(all(old.get(k) == row.get(k) for k in self.conflict) for old in self.db.rows[self.table]):
                    self.db.rows[self.table].append(deepcopy(row)); inserted.append(deepcopy(row))
            return SimpleNamespace(data=inserted)
        result = deepcopy(self.db.rows[self.table])
        for op, field, value in self.filters:
            result = [r for r in result if (r.get(field) == value if op == 'eq' else
                      r[field] >= value if op == 'gte' else r[field] < value)]
        result.sort(key=lambda r: (r.get('time', ''), r.get('id', 0)))
        return SimpleNamespace(data=result[self.bounds[0]:self.bounds[1] + 1], count=len(result))


class DB:
    def __init__(self):
        self.rows = {'symbols': [dict(symbol='SSI', status='active', intraday_status='active')],
                     'stock_raw_intraday': [], 'stock_intraday': []}
        self.calls, self.mutations, self.partitions, self.hook = [], [], [], None
    def get(self): return self
    def table(self, name): return Query(self, name)
    def rpc(self, name, params):
        assert name == 'create_partition_if_not_exists'
        db = self
        class RPC:
            def execute(self):
                db.partitions.append(params)
                return SimpleNamespace(data=None)
        return RPC()


def run(db=None, rows=None, write=False, **kwargs):
    source, _ = adapter(rows=rows)
    return run_manual_intraday('20/10/2026', symbols=['SSI'], db=db or DB(), adapter=source, write=write, **kwargs)


@pytest.mark.parametrize('date,symbols', [
    (None, ['SSI']), ('2026/10/20', ['SSI']), ('2026-02-30', ['SSI']), ('2999-01-01', ['SSI']),
    ('2026-10-20', None), ('2026-10-20', []), ('2026-10-20', ['SSI', 'HPG']),
    ('2026-10-20', ['SSI', 'SSI']), ('2026-10-20', ['*']), ('2026-10-20', ['ALL']),
    ('2026-10-20', ['SSI,HPG']), ('2026-10-20', ['SSI?']), ('2026-10-20', ['']),
])
def test_scope_rejected_before_clients(date, symbols, monkeypatch):
    def fail(*a, **kw): raise AssertionError('client construction')
    monkeypatch.setattr('src.ingest.stock_intraday.manual.SSIV3Adapter', fail)
    monkeypatch.setattr('src.ingest.stock_intraday.manual.SupabaseClient', fail)
    with pytest.raises(ValueError):
        run_manual_intraday(date, symbols=symbols, write=True)


def test_source_is_intraday_preview_only():
    with pytest.raises(ValueError, match='unsupported data source'):
        scope('2026-10-20', ['SSI'], 'ssi_v2')
    from src.providers.ssi.registry import resolve_source
    with pytest.raises(ValueError, match='no production-ready'):
        resolve_source('stock_intraday')
    assert scope('2026-10-20', ['ssi'], 'ssi_v3')[1] == 'SSI'


@pytest.mark.parametrize('write', [False, True])
def test_raw_clean_roundtrip_and_repeat_noop(write):
    db = DB()
    rows = [candle('16'), candle('15')]
    original = deepcopy(rows)
    result = run(db, rows, write)
    assert result['status'] == 'OK', result
    assert result['mode'] == ('WRITE' if write else 'DRY_RUN')
    assert result['received_order'] == 'descending'
    assert result['completeness_status'] == 'UNVERIFIED'
    assert not any(w['code'] == 'INTRADAY_UNSORTED_INPUT' for w in result['validation_warnings'])
    assert rows == original
    assert result['utc_scope'] == ['2026-10-19T17:00:00Z', '2026-10-20T17:00:00Z']
    if not write:
        assert db.mutations == db.partitions == []
        assert result['raw_inserted'] == result['clean_inserted'] == 0
        assert result['planned_raw_insert'] == result['planned_clean_insert'] == 2
        return
    assert result['raw_inserted'] == result['clean_inserted'] == 2
    assert [m[0] for m in db.mutations] == ['stock_raw_intraday', 'stock_intraday']
    assert db.rows['stock_raw_intraday'][0]['payload'] == rows[0]
    assert db.rows['stock_raw_intraday'][0]['source'] == 'ssi_v3'
    clean = db.rows['stock_intraday'][0]
    assert clean['value'] == 999999 != clean['close'] * clean['volume']
    assert clean['time'] == '2026-10-20T02:16:00Z' and clean['timeframe'] == '1m'
    assert db.partitions == [{'p_table': 'stock_intraday', 'p_time': '2026-10-01T00:00:00Z'}]
    before = deepcopy(db.rows)
    mutations, partitions = len(db.mutations), len(db.partitions)
    repeated = run(db, rows, True)
    assert repeated['status'] == 'OK'
    assert repeated['raw_inserted'] == repeated['clean_inserted'] == 0
    assert repeated['raw_skipped_existing'] == repeated['clean_skipped_existing'] == 2
    assert db.rows == before and len(db.mutations) == mutations and len(db.partitions) == partitions


@pytest.mark.parametrize('changes', [dict(value=None), dict(value=''), dict(value='1.5'), dict(value='-1'),
    dict(value='NaN'), dict(value=str(2**63)), dict(volume='1.1'), dict(volume='-1'),
    dict(high='8'), dict(open='NaN'), dict(symbol='HPG'), dict(tradingDate='2026/10/21 09:15:00')])
def test_bad_candle_blocks_entire_batch(changes):
    row = candle(); row.update(changes)
    db = DB()
    result = run(db, [candle('16'), row], True)
    assert result['status'] == 'BLOCKED', result
    assert not db.mutations and not db.partitions


def test_missing_value_and_missing_identity_block():
    for field in ['value', 'symbol']:
        row = candle(); row.pop(field)
        db = DB()
        assert run(db, [row], True)['status'] == 'BLOCKED'
        assert not db.mutations


@pytest.mark.parametrize('rows', [[candle(), candle()], [candle('15'), candle('17'), candle('16')]])
def test_duplicates_and_mixed_block(rows):
    db = DB()
    assert run(db, rows, True)['status'] == 'BLOCKED'
    assert not db.mutations


@pytest.mark.parametrize('bodies,options', [
    ([{'data': []}], {}), ([{'code': 204, 'msg': 'No Content'}], {}),
    ([{'code': 500, 'msg': 'bad'}], {}), ([{'data': [candle()]}], {'max_pages': 1}),
])
def test_empty_errors_truncation_block(bodies, options):
    db = DB(); source, _ = adapter(bodies=bodies, **options)
    result = run_manual_intraday('2026-10-20', symbols=['SSI'], adapter=source, db=db, write=True)
    assert result['status'] == 'BLOCKED', result
    assert not db.mutations and not db.partitions


def test_multipage_204_complete():
    source, session = adapter(bodies=[{'data': [candle('16')]}, {'data': [candle()]}, {'code': 204, 'msg': 'No Content'}])
    result = run_manual_intraday('2026-10-20', symbols=['SSI'], adapter=source, db=DB(), write=True)
    assert result['status'] == 'OK' and result['pagination_termination'] == 'provider_no_content_204'
    assert [q['params']['pageIndex'] for q in session.calls] == [1, 2, 3]


@pytest.mark.parametrize('field', ['status', 'intraday_status'])
def test_ineligible_blocks_before_fetch(field):
    db = DB(); db.rows['symbols'][0][field] = 'inactive'
    source, session = adapter()
    result = run_manual_intraday('2026-10-20', symbols=['SSI'], db=db, adapter=source, write=True)
    assert result['status'] == 'BLOCKED' and field in result['failures'][0]
    assert not session.calls and not db.mutations


@pytest.mark.parametrize('table,field,value', [('stock_intraday', 'value', 123),
    ('stock_raw_intraday', 'source', 'SSI_v2'), ('stock_raw_intraday', 'payload', None)])
def test_existing_conflict_blocks_before_either_write(table, field, value):
    db = DB(); assert run(db, write=True)['status'] == 'OK'
    db.rows[table][0][field] = value
    db.mutations.clear(); db.partitions.clear()
    result = run(db, write=True)
    assert result['status'] == 'BLOCKED' and result['conflict_count'] == 1
    assert field in result['conflicts'][0]['fields']
    assert not db.mutations and not db.partitions


def test_partial_failure_and_safe_recovery():
    db = DB()
    def fail(q):
        if q.table == 'stock_intraday': raise RuntimeError('test clean failure')
    db.hook = fail
    result = run(db, write=True)
    assert result['status'] == 'PARTIAL' and result['failed_stage'] == 'clean_insert'
    assert result['raw_inserted'] == 1 and not result['insert_counts_confirmed']
    assert len(db.rows['stock_raw_intraday']) == 1 and not db.rows['stock_intraday']
    db.hook = None
    result = run(db, write=True)
    assert result['status'] == 'OK' and result['raw_inserted'] == 0 and result['clean_inserted'] == 1


@pytest.mark.parametrize('table', ['stock_raw_intraday', 'stock_intraday'])
def test_concurrent_conflict_is_never_overwritten(table):
    db = DB()
    def race(q):
        if q.table == table:
            row = deepcopy(q.rows[0])
            row['source' if table == 'stock_raw_intraday' else 'value'] = 'v2' if table == 'stock_raw_intraday' else 1
            db.rows[table].append(row)
    db.hook = race
    result = run(db, write=True)
    assert result['status'] == 'PARTIAL', result
    assert db.rows[table][0].get('source' if table == 'stock_raw_intraday' else 'value') == ('v2' if table == 'stock_raw_intraday' else 1)
    if table == 'stock_raw_intraday': assert not db.rows['stock_intraday']


def test_missing_readback_detected():
    db = DB()
    original = db.table
    def table(name):
        q = original(name)
        old = q.execute
        def execute():
            response = old()
            if name == 'stock_intraday' and q.operation == 'read' and db.mutations:
                response.data = []
            return response
        q.execute = execute
        return q
    db.table = table
    result = run(db, write=True)
    assert result['status'] == 'PARTIAL' and result['failed_stage'] == 'final_readback'


def test_hash_canonical_not_fetch_time():
    row = candle()
    assert semantic_hash(row) == semantic_hash(dict(reversed(list(row.items()))))
    assert semantic_hash(row) != semantic_hash({**row, 'value': '2'})


def test_unrelated_scope_untouched_and_paged_reads():
    db = DB()
    db.rows['stock_raw_intraday'] = [dict(id=i, symbol='SSI', time='2026-10-20T03:00:00Z',
        data_hash=str(i), source='old', payload=None) for i in range(205)]
    db.rows['stock_intraday'] = [dict(symbol='HPG', timeframe='1m', time='2026-10-20T03:00:00Z'),
                                dict(symbol='SSI', timeframe='1m', time='2026-10-21T03:00:00Z')]
    original = deepcopy(db.rows)
    result = run(db, write=True)
    assert result['status'] == 'OK', result
    assert result['readback_raw_count'] == 206 and result['readback_clean_count'] == 1
    assert db.rows['stock_intraday'][:2] == original['stock_intraday']
    assert db.rows['stock_raw_intraday'][:205] == original['stock_raw_intraday']
    reads = [filters for table, op, filters in db.calls if table in ('stock_raw_intraday', 'stock_intraday') and op == 'read']
    assert all(('eq', 'symbol', 'SSI') in f and ('gte', 'time', '2026-10-19T17:00:00Z') in f and
               ('lt', 'time', '2026-10-20T17:00:00Z') in f for f in reads)


def test_no_database_credentials_readonly_plan_unknown(monkeypatch):
    monkeypatch.setattr('src.ingest.stock_intraday.manual.config.SUPABASE_URL', None)
    source, _ = adapter()
    result = run_manual_intraday('2026-10-20', symbols=['SSI'], adapter=source)
    assert result['status'] == 'OK' and not result['write_ready']
    assert result['db_preflight'] == 'NOT_RUN_NO_CREDENTIALS'
    assert result['planned_raw_insert'] is None and result['raw_inserted'] == 0
    result = run_manual_intraday('2026-10-20', symbols=['SSI'], adapter=source, write=True)
    assert result['status'] == 'BLOCKED'


def test_unknown_master_blocks_before_source():
    db = DB(); db.rows['symbols'] = []
    source, session = adapter()
    result = run_manual_intraday('2026-10-20', symbols=['SSI'], db=db, adapter=source, write=True)
    assert result['status'] == 'BLOCKED' and result['failed_stage'] == 'eligibility'
    assert not session.calls and not db.mutations


def test_http_failure_blocks_before_writes():
    import requests
    source, _ = adapter(bodies=[requests.HTTPError('offline HTTP failure')])
    db = DB()
    result = run_manual_intraday('2026-10-20', symbols=['SSI'], db=db, adapter=source, write=True)
    assert result['status'] == 'BLOCKED' and not db.mutations and not db.partitions


def test_zero_source_value_preserved_not_estimated():
    row = candle(); row['value'] = '0'
    db = DB(); result = run(db, [row], True)
    assert result['status'] == 'OK' and db.rows['stock_intraday'][0]['value'] == 0


def test_acknowledged_raw_batches_retained_after_later_failure():
    from datetime import datetime, timedelta
    rows = []
    for i in range(101):
        row = candle()
        row['tradingDate'] = (datetime(2026, 10, 20, 9) + timedelta(minutes=i)).strftime('%Y/%m/%d %H:%M:%S')
        rows.append(row)
    db = DB()
    def fail_second(q):
        if q.table == 'stock_raw_intraday' and len(db.mutations) == 2:
            raise RuntimeError('second request outcome unknown')
    db.hook = fail_second
    result = run(db, rows, True)
    assert result['status'] == 'PARTIAL' and result['raw_inserted'] == 100
    assert not result['insert_counts_confirmed'] and not db.rows['stock_intraday']


def test_truncated_database_response_is_blocked_before_writes():
    db = DB(); original = db.table
    def table(name):
        q = original(name); execute = q.execute
        def truncated():
            response = execute()
            if name == 'stock_intraday' and q.operation == 'read':
                response.count = len(response.data) + 1
            return response
        q.execute = truncated
        return q
    db.table = table
    result = run(db, write=True)
    assert result['status'] == 'BLOCKED' and not db.mutations


def test_extra_historical_clean_timestamp_blocks_before_mutation():
    db = DB(); assert run(db, write=True)['status'] == 'OK'
    extra = deepcopy(db.rows['stock_intraday'][0]); extra['time'] = '2026-10-20T03:00:00Z'
    db.rows['stock_intraday'].append(extra); db.mutations.clear(); db.partitions.clear()
    result = run(db, write=True)
    assert result['status'] == 'BLOCKED' and result['conflicts'][0]['fields'] == ['unexpected_timestamp']
    assert not db.mutations and not db.partitions
