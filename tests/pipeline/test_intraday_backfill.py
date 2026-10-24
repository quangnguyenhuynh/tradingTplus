"""Guarded range orchestration and real manual-path integration with offline fakes."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import runpy
import socket

import pytest
import requests

import src.cli as cli
import src.cli.maintenance as handler
import importlib
pipeline = importlib.import_module('src.ingest.maintenance.backfill')
manual = importlib.import_module('src.ingest.stock_intraday.manual')
# Reuse the pilot's fake PostgREST boundary and fake SSI session, not a second
# persistence or mapping implementation. All fixture candles are synthetic.
fakes = runpy.run_path(str(Path('tests/ingest/test_manual_intraday.py')))
DB, source_adapter = fakes['DB'], fakes['adapter']


def ok_pair(day, *, symbols, data_source, write):
    return dict(status='OK', symbol=symbols[0], date=day, db_preflight='PASS', write_ready=True,
                raw_received=2, mapped_valid=2, pagination_complete=True, validation_status='PASS',
                raw_inserted=2 if write else 0, clean_inserted=2 if write else 0,
                raw_skipped_existing=0, clean_skipped_existing=0, planned_raw_insert=2, planned_clean_insert=2,
                conflict_count=0, systemic_failure=False)


@pytest.fixture(autouse=True)
def no_unapproved_services(monkeypatch):
    attempts = []
    def fail(*a, **kw):
        attempts.append(True)
        raise AssertionError('unexpected network/client/downstream execution')
    monkeypatch.setattr(requests.sessions.Session, 'request', fail)
    monkeypatch.setattr(socket, 'create_connection', fail)
    monkeypatch.setattr(manual, 'SupabaseClient', fail)
    monkeypatch.setattr(manual, 'SSIV3Adapter', fail)
    monkeypatch.setattr(pipeline, 'run_daily_ingest', fail)
    monkeypatch.setattr(pipeline, 'run_intraday_ingest', fail)
    monkeypatch.setattr(pipeline, 'check_ingest', fail)
    yield
    assert not attempts


def run(*, symbols=('SSI',), start='19/10/2026', end='21/10/2026', write=False, **kwargs):
    return pipeline.run_intraday_backfill_pipeline(start, end, symbols=list(symbols), write=write, **kwargs)


@pytest.mark.parametrize('symbols,days', [(['SSI'], 1), (['SSI', 'HPG'], 1), (['SSI'], 3), (['SSI', 'HPG'], 3)])
@pytest.mark.parametrize('write', [False, True])
def test_deterministic_pairs_and_aggregate(symbols, days, write, monkeypatch):
    calls = []
    def pilot(day, **kw): calls.append((day, kw)); return ok_pair(day, **kw)
    monkeypatch.setattr(pipeline, 'run_manual_intraday', pilot)
    result = run(symbols=symbols, end='19/10/2026' if days == 1 else '21/10/2026', write=write)
    assert result['status'] == 'OK' and result['flow'] == 'backfill-intraday'
    assert [(day, kw['symbols'][0]) for day, kw in calls] == [(f'{d}/10/2026', s) for d in range(19, 19 + days) for s in symbols]
    assert all(kw['data_source'] == 'ssi_v3' and kw['write'] is write for _, kw in calls)
    count = len(symbols) * days
    assert result['planned_pairs'] == result['processed_pairs'] == result['ok_pairs'] == count
    assert result['raw_received'] == result['mapped_valid'] == 2 * count
    assert result['raw_inserted'] == result['clean_inserted'] == (2 * count if write else 0)
    assert result['planned_raw_insert'] == result['planned_clean_insert'] == 2 * count
    assert result['completeness_status'] == 'UNVERIFIED'


@pytest.mark.parametrize('start,end,expected', [('17/10/2026', '18/10/2026', 0), ('16/10/2026', '19/10/2026', 2)])
def test_weekends_no_guessed_holidays(start, end, expected, monkeypatch):
    monkeypatch.setattr(pipeline, 'run_manual_intraday', ok_pair)
    result = run(start=start, end=end)
    assert result['status'] == 'OK' and result['processed_pairs'] == expected
    assert result['skipped_weekend_dates'] == ['17/10/2026', '18/10/2026']
    assert result['requested_calendar_days'] == (2 if not expected else 4)
    assert result['write_ready'] is bool(expected)


@pytest.mark.parametrize('args', [dict(from_date='bad'), dict(from_date='2026-10-22', to_date='2026-10-21'),
    dict(to_date='2999-01-01'), dict(symbols=None), dict(symbols=[]), dict(symbols=['ALL']), dict(symbols=['*']),
    dict(symbols=['SSI,HPG']), dict(symbols=['SSI?']), dict(symbols=['']), dict(symbols=['SSI', ' ']),
    dict(symbols=[None]), dict(data_source='ssi_v2'), dict(write='yes'),
    dict(from_date='2026-01-01', to_date='2026-10-21'), dict(from_date='0001-01-01', to_date='2026-10-21')])
def test_scope_rejected_before_pilot(args, monkeypatch):
    monkeypatch.setattr(pipeline, 'run_manual_intraday', lambda *a, **k: pytest.fail('pilot called'))
    kwargs = dict(from_date='2026-10-19', to_date='2026-10-21', symbols=['SSI']); kwargs.update(args)
    with pytest.raises(ValueError): pipeline.run_intraday_backfill_pipeline(**kwargs)


def test_exact_limit_and_symbol_normalization(monkeypatch):
    monkeypatch.setattr(pipeline, 'run_manual_intraday', ok_pair)
    result = run(start='2026-10-05', end='2026-10-16', symbols=[' ssi ', 'HPG', 'SSI', 'AAA', 'BBB', 'CCC'])
    assert result['planned_pairs'] == 50 and result['requested_symbols'] == ['SSI', 'HPG', 'AAA', 'BBB', 'CCC']
    with pytest.raises(ValueError, match='50'):
        run(start='2026-10-05', end='2026-10-16', symbols=['SSI', 'HPG', 'AAA', 'BBB', 'CCC', 'DDD'])


@pytest.mark.parametrize('bad_status', ['BLOCKED', 'FAILED', 'PARTIAL', 'NO_SOURCE_DATA'])
def test_pair_failure_continues_and_status_not_false_success(bad_status, monkeypatch):
    calls = []
    def pilot(day, **kw):
        calls.append((day, kw['symbols'][0])); result = ok_pair(day, **kw)
        if len(calls) == 1:
            result.update(status=bad_status, error_category='PAIR_TEST', write_ready=False)
            if bad_status == 'NO_SOURCE_DATA':
                result.update(status='BLOCKED', source_status='EMPTY', raw_received=0, mapped_valid=0)
        return result
    monkeypatch.setattr(pipeline, 'run_manual_intraday', pilot)
    result = run(symbols=['SSI', 'HPG'])
    assert len(calls) == 6 and result['status'] == 'PARTIAL' and result['ok_pairs'] == 5
    assert result['error_count'] == 1 and not result['write_ready']


@pytest.mark.parametrize('partial', [False, True])
def test_systemic_failure_stops_remaining_pairs(partial, monkeypatch):
    calls = []
    def pilot(day, **kw):
        calls.append(day); report = ok_pair(day, **kw)
        if len(calls) == (2 if partial else 1):
            report.update(status='BLOCKED', error_category='SSI_AUTH_CONFIGURATION', systemic_failure=True, write_ready=False)
        return report
    monkeypatch.setattr(pipeline, 'run_manual_intraday', pilot)
    result = run(symbols=['SSI', 'HPG'])
    assert result['status'] == ('PARTIAL' if partial else 'FAILED') and result['halted']
    assert result['unprocessed_pairs'] == (4 if partial else 5)
    assert result['halt_reason'] == 'SSI_AUTH_CONFIGURATION'


@pytest.fixture
def integration(monkeypatch):
    db = DB(); db.rows['symbols'].append(dict(symbol='HPG', status='active', intraday_status='active'))
    captures = []
    changes = {}
    def adapter_factory():
        class Adapter:
            def preview_intraday(self, symbol, day, **kw):
                captures.append((symbol, day))
                row = dict(symbol=symbol, tradingDate=day.replace('-', '/') + ' 09:15:17',
                           open='10', high='11', low='9', close='10', volume='100', value='9007199254740993')
                rule = changes.get((symbol, day), {})
                row.update(rule.get('row', {}))
                bodies = rule.get('bodies', [{'data': [row]}, {'code': 204, 'msg': 'No Content'}])
                adapter, _ = source_adapter(bodies=bodies, **rule.get('options', {}))
                return adapter.preview_intraday(symbol, day, **kw)
        return Adapter()
    monkeypatch.setattr(manual, 'SupabaseClient', lambda: db)
    monkeypatch.setattr(manual, 'SSIV3Adapter', adapter_factory)
    monkeypatch.setattr(manual.config, 'SUPABASE_URL', 'https://offline.invalid')
    monkeypatch.setattr(manual.config, 'SUPABASE_SERVICE_KEY', 'offline-test-only')
    return db, captures, changes


@pytest.mark.parametrize('write', [False, True])
def test_real_pilot_safety_idempotency_scope_and_bigint(integration, write):
    db, captures, _ = integration
    untouched = dict(symbol='OTHER', timeframe='15m', time='2026-10-20T02:15:17Z', value=5)
    db.rows['stock_intraday'].append(untouched)
    result = run(symbols=['SSI', 'HPG'], write=write)
    assert result['status'] == 'OK', result
    assert len(captures) == 6
    assert result['raw_inserted'] == result['clean_inserted'] == (6 if write else 0)
    if not write:
        assert not db.mutations and not db.partitions
        assert result['planned_raw_insert'] == result['planned_clean_insert'] == 6
        return
    assert all(row['source'] == 'ssi_v3' and row['payload']['value'] == '9007199254740993' for row in db.rows['stock_raw_intraday'])
    assert all(row['value'] == 9007199254740993 and row['timeframe'] == '1m' for row in db.rows['stock_intraday'][1:])
    assert db.rows['stock_intraday'][0] == untouched
    assert result['per_symbol_date'][0]['utc_scope'] == ['2026-10-18T17:00:00Z', '2026-10-19T17:00:00Z']
    before = deepcopy(db.rows); partition_count = len(db.partitions)
    repeat = run(symbols=['SSI', 'HPG'], write=True)
    assert repeat['status'] == 'OK' and repeat['raw_inserted'] == repeat['clean_inserted'] == 0
    assert repeat['raw_skipped_existing'] == repeat['clean_skipped_existing'] == 6
    assert db.rows == before and len(db.partitions) == partition_count


@pytest.mark.parametrize('field,value', [('value', None), ('value', '-1'), ('volume', '1.5'), ('high', '8')])
def test_invalid_source_pair_does_not_write_subset_and_later_pair_runs(integration, field, value):
    db, captures, changes = integration
    changes[('SSI', '2026-10-19')] = {'row': {field: value}}
    result = run(write=True)
    assert result['status'] == 'PARTIAL' and result['blocked_pairs'] == 1 and result['ok_pairs'] == 2
    assert result['raw_inserted'] == result['clean_inserted'] == 2 and len(captures) == 3
    assert not any(r['time'].startswith('2026-10-19') for r in db.rows['stock_raw_intraday'])


def test_explicit_empty_not_holiday_success(integration):
    db, _, changes = integration
    changes[('SSI', '2026-10-19')] = {'bodies': [{'code': 204, 'msg': 'No Content'}]}
    result = run(end='19/10/2026', write=True)
    assert result['status'] == 'FAILED' and result['no_source_data_pairs'] == 1
    pair = result['per_symbol_date'][0]
    assert pair['status'] == 'NO_SOURCE_DATA' and pair['pagination_complete'] and pair['completeness_status'] == 'UNVERIFIED'
    assert not db.mutations and not db.partitions


@pytest.mark.parametrize('kind', ['incomplete', 'duplicates', 'unsupported', 'auth'])
def test_source_failure_policy(integration, kind):
    db, captures, changes = integration
    row = dict(symbol='SSI', tradingDate='2026/10/19 09:15:00', open='10', high='10', low='10', close='10', volume='1', value='5')
    rule = {'incomplete': {'bodies': [{'data': [row]}], 'options': {'max_pages': 1}},
            'duplicates': {'bodies': [{'data': [row, row]}, {'code': 204, 'msg': 'No Content'}]},
            'unsupported': {'bodies': [{'code': 400, 'msg': 'historical scope unavailable'}]},
            'auth': {'bodies': [{'code': 401, 'msg': 'unauthorized'}]}}[kind]
    changes[('SSI', '2026-10-19')] = rule
    result = run(write=True)
    assert result['status'] == ('FAILED' if kind == 'auth' else 'PARTIAL'), result
    assert len(captures) == (1 if kind == 'auth' else 3)
    assert not any(r['time'].startswith('2026-10-19') for r in db.rows['stock_raw_intraday'])
    if kind == 'auth': assert result['halted'] and not db.partitions


@pytest.mark.parametrize('control', ['status', 'intraday_status'])
def test_master_control_blocks_only_requested_symbol(integration, control):
    db, captures, _ = integration
    db.rows['symbols'][0][control] = 'inactive'
    result = run(symbols=['SSI', 'HPG'], write=True)
    assert result['blocked_pairs'] == 3 and result['ok_pairs'] == 3 and result['status'] == 'PARTIAL'
    assert all(symbol == 'HPG' for symbol, _ in captures)
    assert control in result['per_symbol_date'][0]['failures'][0]


@pytest.mark.parametrize('table,field,value', [('stock_intraday', 'value', 1), ('stock_raw_intraday', 'source', 'SSI')])
def test_historical_conflict_never_overwritten(integration, table, field, value):
    db, _, _ = integration
    assert run(end='19/10/2026', write=True)['status'] == 'OK'
    db.rows[table][0][field] = value
    before = deepcopy(db.rows); db.mutations.clear(); db.partitions.clear()
    result = run(end='19/10/2026', write=True)
    assert result['status'] == 'FAILED' and result['blocked_pairs'] == 1
    assert result['per_symbol_date'][0]['conflict_count'] == 1
    assert db.rows == before and not db.mutations and not db.partitions


def test_partial_raw_clean_failure_and_safe_rerun(integration):
    db, _, _ = integration
    def fail(q):
        if q.table == 'stock_intraday': raise RuntimeError('private failure details')
    db.hook = fail
    result = run(write=True)
    assert result['partial_pairs'] == 1 and result['status'] == 'FAILED' and result['halted']
    assert result['raw_inserted'] == 1 and result['clean_inserted'] == 0 and not result['insert_counts_confirmed']
    assert result['unprocessed_pairs'] == 2
    assert 'private failure details' not in str(result)
    db.hook = None
    result = run(write=True)
    assert result['status'] == 'OK' and result['raw_skipped_existing'] == 1
    assert result['raw_inserted'] == 2 and result['clean_inserted'] == 3


def test_source_only_preview_not_write_approval(integration, monkeypatch):
    db, captures, _ = integration
    monkeypatch.setattr(manual.config, 'SUPABASE_URL', None)
    result = run()
    assert result['status'] == 'FAILED' and result['halted'] and result['blocked_pairs'] == 1
    assert result['processed_pairs'] == 1 and len(captures) == 1
    pair = result['per_symbol_date'][0]
    assert pair['pilot_status'] == 'OK' and pair['db_preflight'] == 'NOT_RUN_NO_CREDENTIALS'
    assert not result['write_ready'] and not db.mutations and not db.partitions


@pytest.mark.parametrize('name', ['stock-intraday-backfill', 'backfill-intraday'])
@pytest.mark.parametrize('flags,write', [([], False), (['--dry-run'], False), (['--write'], True)])
def test_cli_aliases_modes_exit_and_json(name, flags, write, monkeypatch, capsys):
    captured = []
    def runner(*a, **kw): captured.append((a, kw)); return {'flow': 'backfill-intraday', 'status': 'PARTIAL'}
    monkeypatch.setattr(handler, 'run_intraday_backfill_pipeline', runner)
    assert cli.main([name, '--from-date', '2026-10-19', '--to', '2026-10-21', '--symbols', 'ssi', *flags]) == 1
    import json
    assert json.loads(capsys.readouterr().out)['flow'] == 'backfill-intraday'
    assert captured == [(('2026-10-19', '2026-10-21'), {'symbols': ['ssi'], 'write': write})]


@pytest.mark.parametrize('argv', [[], ['--from', '2026-10-19', '--to', '2026-10-21'],
    ['--from', '2026-10-19', '--symbols', 'SSI'],
    ['--from', '2026-10-19', '--to', '2026-10-21', '--symbols', 'SSI', '--write', '--dry-run']])
def test_cli_missing_scope_and_modes_rejected(argv):
    assert cli.main(['stock-intraday-backfill', *argv]) == 2


@pytest.mark.parametrize('bad', ['ALL', '*', 'SSI,HPG'])
def test_cli_invalid_scope_before_services(bad):
    assert cli.main(['stock-intraday-backfill', '--from', '2026-10-19', '--to', '2026-10-21', '--symbols', bad]) == 2


def test_unknown_pair_exception_sanitized_and_halts(monkeypatch):
    def fail(*a, **kw): raise RuntimeError('Authorization: secret-must-not-print')
    monkeypatch.setattr(pipeline, 'run_manual_intraday', fail)
    result = run()
    assert result['status'] == 'FAILED' and result['processed_pairs'] == 1 and result['unprocessed_pairs'] == 2
    assert len(result['unprocessed_symbol_date']) == 2
    assert 'secret-must-not-print' not in str(result)
    pair = result['per_symbol_date'][0]
    assert pair['raw_inserted'] == pair['clean_inserted'] == 0 and pair['recovery']


def test_missing_database_write_stops_before_source(integration, monkeypatch):
    db, captures, _ = integration
    monkeypatch.setattr(manual.config, 'SUPABASE_URL', None)
    result = run(write=True)
    assert result['status'] == 'FAILED' and result['halted'] and not captures
    assert result['per_symbol_date'][0]['error_category'] == 'CONFIGURATION'
    assert not db.mutations and not db.partitions


def test_invalid_global_db_dependency_halts_without_secret(integration, monkeypatch):
    db, captures, _ = integration
    def fail(*a, **kw): raise RuntimeError('database-url=private')
    monkeypatch.setattr(db, 'table', fail)
    result = run(write=True)
    assert result['status'] == 'FAILED' and result['halted'] and not captures
    assert result['per_symbol_date'][0]['error_category'] == 'DB_DEPENDENCY'
    assert 'database-url=private' not in str(result)


def test_existing_extra_timestamp_blocks_without_repair(integration):
    db, _, _ = integration
    assert run(end='19/10/2026', write=True)['status'] == 'OK'
    extra = deepcopy(db.rows['stock_intraday'][0]); extra['time'] = '2026-10-19T02:15:00Z'
    db.rows['stock_intraday'].append(extra)
    before = deepcopy(db.rows); db.mutations.clear(); db.partitions.clear()
    result = run(end='19/10/2026', write=True)
    assert result['status'] == 'FAILED' and result['blocked_pairs'] == 1
    assert db.rows == before and not db.mutations and not db.partitions


def test_mixed_chronology_blocks_whole_pair(integration):
    db, _, changes = integration
    rows = [dict(symbol='SSI', tradingDate=f'2026/10/19 09:{minute}:00', open='10', high='10', low='10', close='10', volume='1', value='9')
            for minute in ('15', '17', '16')]
    changes[('SSI', '2026-10-19')] = {'bodies': [{'data': rows}, {'code': 204, 'msg': 'No Content'}]}
    result = run(end='19/10/2026', write=True)
    assert result['status'] == 'FAILED' and result['per_symbol_date'][0]['received_order'] == 'mixed'
    assert not db.mutations and not db.partitions


def test_no_successful_pair_with_partial_writes_is_not_ok(monkeypatch):
    def partial(day, **kw):
        result = ok_pair(day, **kw)
        result.update(status='PARTIAL', raw_inserted=1, clean_inserted=0, write_ready=False,
                      insert_counts_confirmed=False, failed_stage='clean_insert', error_category='DB_DEPENDENCY', systemic_failure=True)
        return result
    monkeypatch.setattr(pipeline, 'run_manual_intraday', partial)
    result = run(write=True)
    assert result['status'] == 'FAILED' and result['partial_pairs'] == 1 and result['raw_inserted'] == 1
    assert not result['insert_counts_confirmed']


def test_cli_plan_over_limit_before_source():
    assert cli.main(['stock-intraday-backfill', '--from', '01/01/2026', '--to', '21/10/2026', '--symbols', 'SSI']) == 2


@pytest.mark.parametrize('cause', ['network', 'provider_unavailable'])
def test_exhausted_shared_source_dependency_stops(integration, cause):
    db, captures, changes = integration
    body = requests.ConnectionError('private-network-detail') if cause == 'network' else {'code': 503, 'msg': 'shared dependency unavailable'}
    changes[('SSI', '2026-10-19')] = {'bodies': [body]}
    result = run(write=True)
    assert result['status'] == 'FAILED' and result['halted'] and len(captures) == 1
    assert result['halt_reason'] == 'SSI_SHARED_DEPENDENCY'
    assert result['planned_raw_insert'] is None and result['planned_clean_insert'] is None
    assert not db.mutations and not db.partitions


def test_no_credential_source_error_stops_as_systemic(integration, monkeypatch):
    # Exercise the actual pilot's source exception path, without any request.
    db, _, _ = integration
    class BrokenSource:
        def preview_intraday(self, *a, **kw): raise ValueError('private-config-details')
    monkeypatch.setattr(manual, 'SSIV3Adapter', BrokenSource)
    result = run()
    assert result['status'] == 'FAILED' and result['halted'] and result['processed_pairs'] == 1
    assert result['halt_reason'] == 'SSI_SHARED_DEPENDENCY'
    assert 'private-config-details' not in str(result)
    assert not db.mutations


def test_empty_source_without_db_preflight_stops_safely(integration, monkeypatch):
    db, captures, changes = integration
    monkeypatch.setattr(manual.config, 'SUPABASE_URL', None)
    changes[('SSI', '2026-10-19')] = {'bodies': [{'code': 204, 'msg': 'No Content'}]}
    result = run()
    assert result['status'] == 'FAILED' and result['halted'] and len(captures) == 1
    assert result['no_source_data_pairs'] == 1 and result['halt_reason'] == 'DB_PREFLIGHT_UNVERIFIED'
    assert result['per_symbol_date'][0]['pagination_complete']
    assert not result['write_ready'] and not db.mutations and not db.partitions
