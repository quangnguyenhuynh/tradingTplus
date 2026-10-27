"""Mock HTTP contract tests. Samples are representative, not verbatim SSI rows."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json
from pathlib import Path
import runpy
import socket

import pytest
import requests

from src.cli import main
from src.ingest.master.sync import run_master_sync
from src.ingest.master.store import MasterStore
from src.providers.ssi.adapters.master_v3 import (
    SSIV3MasterAdapter, BOARDS, MAPPING_VERSION, map_verified_record, OWNER_REFERENCE,
)
from src.providers.ssi.clients.rest_v3 import SSIV3Client, SSIReadError, master_retry_delay
from src.providers.ssi.master_registry import MASTER_REGISTRY, MasterRegistry

MemoryClient = runpy.run_path('tests/ingest/test_versioned_master_sync.py')['MemoryClient']
SAMPLES = json.loads(Path('tests/fixtures/data_preview/ssi_v3_master_contract_samples.json').read_text())
REFERENCE = {'date': 'synthetic offline reference', 'counts': {b: len(SAMPLES[b]) for b in BOARDS}}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def fail(*a, **kw): raise AssertionError('Real network/DB/downstream accessed')
    monkeypatch.setattr(requests.sessions.Session, 'request', fail)
    monkeypatch.setattr(socket, 'create_connection', fail)
    monkeypatch.setattr('src.database.client.SupabaseClient._connect', fail)
    monkeypatch.setattr('src.ingest.stock_daily.daily.run_daily_ingest', fail)
    monkeypatch.setattr('src.ingest.stock_intraday.manual.run_manual_intraday', fail)
    monkeypatch.setattr('src.ingest.index_daily.index_daily.run_index_daily_ingest', fail)
    monkeypatch.setattr('src.config.config.SSI_API_KEY', 'synthetic-api-key')
    monkeypatch.setattr('src.config.config.SSI_API_SECRET', 'synthetic-api-secret')
    monkeypatch.setattr('time.sleep', lambda _: None)


def response(value=None, status=200, *, raw=None, headers=None):
    r = requests.Response()
    r.status_code = status
    r._content = json.dumps(value, ensure_ascii=False).encode() if raw is None else raw
    r.headers.update(headers or {})
    return r


class Session:
    def __init__(self, responses): self.responses, self.calls = list(responses), []
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        assert self.responses, 'Unexpected HTTP call'
        result = self.responses.pop(0)
        if isinstance(result, Exception): raise result
        return result


def adapter(samples=None, *, before=(), reference=REFERENCE):
    samples = deepcopy(SAMPLES if samples is None else samples)
    session = Session([response({'accessToken': 'synthetic-token'}), *before,
                       *(response(samples[b]) for b in BOARDS)])
    client = SSIV3Client(session=session)
    return SSIV3MasterAdapter(client, reference=reference), session


def run(adapter, dataset='symbols', *, write=False, rows=(), memory=None):
    memory = memory or MemoryClient(dataset, rows)
    capability = replace(MASTER_REGISTRY.resolve(dataset), factory=lambda: adapter)
    result = run_master_sync(dataset, data_source='ssi_v3', write=write,
                             registry=MasterRegistry([capability]),
                             store_factory=lambda: MasterStore(memory))
    return result['datasets'][0], memory


@pytest.mark.parametrize('dataset', ['symbols'])
def test_all_three_boards_and_mappings(dataset):
    a, session = adapter()
    snap = a.fetch(dataset)
    assert snap.complete and snap.source_records == len(snap.records) == 8
    assert snap.mapping_version == MAPPING_VERSION
    assert [call[2]['params'] for call in session.calls[1:]] == [{'board': b} for b in BOARDS]
    assert all('/api/v3/data/securitiesByBoard' in c[1] for c in session.calls[1:])
    assert len(session.calls) == 4 and all(c[0] == 'GET' for c in session.calls[1:])
    assert snap.pagination['authoritative_market_completeness'] == 'UNVERIFIED'
    assert snap.pagination['provider_reported_total'] is None
    by_symbol = {r['symbol']: r for r in snap.records}
    ssi = by_symbol['SSI']
    assert (ssi['name'], ssi['stock_en_name'], ssi['market'], ssi['exchange'], ssi['sec_type']) == (
        'Chứng khoán mẫu', 'Sample Securities', 'HOSE', 'HOSE', 'Stock')
    assert ssi['listed_share'] == '9007199254740993'
    assert ssi['first_trading_date'] == '2006-12-15' and ssi['maturity_date'] is None
    assert by_symbol['UPSTOCK']['first_trading_date'] == '2026-01-27'
    assert by_symbol['BOND202610270001']['sec_type'] == 'Bond'
    assert by_symbol['E1SAMPLE']['sec_type'] == 'ETF Product'
    assert by_symbol['FUNDSAMPLE']['sec_type'] == 'Investment Fund'
    assert by_symbol['UNKNOWNTYPE']['sec_type'] == 'New instrument class'
    assert by_symbol['NULLTYPE']['sec_type'] is None
    assert by_symbol['HNXSTOCK']['stock_en_name'] is None
    assert by_symbol['HNXSTOCK']['listed_share'] is None
    assert 'issuer' not in ssi and 'cwUnderlyingSymbol' not in ssi
    assert ssi['raw']['symbolNameVi'] == 'Chứng khoán mẫu'
    types = snap.pagination['boards'][-1]['unknown_security_types']
    assert types == {'New instrument class': 1, '<NULL>': 1}


@pytest.mark.parametrize('dataset', ['symbols'])
@pytest.mark.parametrize('field,value', [
    ('symbol', None), ('symbol', ''), ('symbol', {}), ('symbol', '*'), ('symbol', True),
    ('board', None), ('board', 'HNX'), ('board', 'upcom'), ('board', 10),
    ('stockType', {}), ('stockType', 1), ('symbolNameVi', []),
    ('lotSize', 'invalid'), ('lotSize', '-1'), ('listedShare', 'NaN'),
    ('listedShare', True), ('firstTradingDate', '2026/02/30'),
    ('firstTradingDate', '2026/01/27 trailing'), ('maturityDate', 'not a date'),
    ('lastTradingDate', 20260127),
])
def test_invalid_source_blocks_entire_dataset(dataset, field, value):
    samples = deepcopy(SAMPLES); samples['HOSE'][0][field] = value
    a, _ = adapter(samples)
    report, memory = run(a, dataset, write=True)
    assert report['status'] == 'FAILED' and memory.writes == []
    assert report['pagination']['boards'][0]['status'] == 'FAILED'
    assert report['planned_inserts'] is None and report['source_missing_records'] is None


@pytest.mark.parametrize('across', [True, False])
def test_duplicate_normalized_identities(across):
    samples = deepcopy(SAMPLES)
    board = 'HNX' if across else 'HOSE'
    samples[board][1]['symbol'] = ' ssi '
    a, _ = adapter(samples)
    report, memory = run(a, write=True)
    assert report['status'] == 'FAILED' and not memory.writes
    assert 'DUPLICATE_SOURCE_IDENTITY' in {e['code'] for e in report['errors']}


@pytest.mark.parametrize('board', BOARDS)
def test_empty_board_blocks_without_missing_conclusions(board):
    samples = deepcopy(SAMPLES); samples[board] = []
    a, session = adapter(samples)
    report, memory = run(a, write=True)
    assert report['status'] == 'FAILED' and not memory.writes
    assert report['source_missing_records'] is None and len(session.calls) == 4
    assert 'SOURCE_BOARD_EMPTY' in {e['code'] for e in report['errors']}


@pytest.mark.parametrize('value', [None, {}, {'data': []}, {'code': 200, 'data': []}, {'code': 503}])
def test_unverified_envelopes_never_become_empty_success(value):
    a, _ = adapter(before=[response(value)])
    report, memory = run(a, write=True)
    assert report['status'] == 'FAILED' and not memory.writes


@pytest.mark.parametrize('raw', [b'[{"symbol":', b'not JSON', b'[{"symbol":"A","symbol":"B"}]',
                               b'[{"x":NaN}]', b'[{"x":Infinity}]'])
def test_malformed_or_ambiguous_json(raw):
    a, _ = adapter(before=[response(raw=raw)])
    report, memory = run(a, write=True)
    assert 'SSI_MALFORMED_JSON' in {e['code'] for e in report['errors']}
    assert not memory.writes and report['status'] == 'FAILED'


@pytest.mark.parametrize('status,code', [(204,'SSI_HTTP_ERROR'), (302,'SSI_HTTP_ERROR'),
    (401,'SSI_AUTH_FAILED'), (403,'SSI_AUTH_FAILED'), (404,'SSI_HTTP_ERROR'),
    (429,'SSI_RATE_LIMIT'), (500,'SSI_HTTP_ERROR'), (503,'SSI_HTTP_ERROR')])
def test_http_statuses_safe_bounded_and_no_database_write(status, code):
    a, session = adapter()
    session.responses = [session.responses[0]] + [response({'error':'synthetic-token'}, status,
                           headers={'Retry-After':'90'})] * 3
    report, memory = run(a, write=True)
    assert report['status'] == 'FAILED' and code in {e['code'] for e in report['errors']}
    assert not memory.writes and 'synthetic-token' not in json.dumps(report)
    assert len(session.calls) == 4  # no early retry of >30s Retry-After


def test_rate_limit_respects_retry_after_and_reuses_auth(monkeypatch):
    sleeps = []; monkeypatch.setattr('time.sleep', sleeps.append)
    a, session = adapter(before=[response({}, 429, headers={'Retry-After': '2'})])
    snap = a.fetch('symbols')
    assert snap.complete and sleeps == [2]
    assert len(session.calls) == 5 and session.calls[1][2]['params'] == session.calls[2][2]['params']
    assert all('Authorization' in call[2]['headers'] for call in session.calls[1:])


def test_rate_limit_retry_bound(monkeypatch):
    sleeps = []; monkeypatch.setattr('time.sleep', sleeps.append)
    a, session = adapter()
    # Three failed attempts per board, plus one auth.
    session.responses = [response({'accessToken':'synthetic-token'})] + [response({},429)] * 9
    report, memory = run(a, write=True)
    assert not memory.writes and len(session.calls) == 10 and len(sleeps) == 6
    assert {e['code'] for e in report['errors']} >= {'SSI_RATE_LIMIT'}


@pytest.mark.parametrize('exc,code,attempts', [
    (requests.Timeout('secret'), 'SSI_TIMEOUT', 3),
    (requests.ConnectionError('secret'), 'SSI_NETWORK_ERROR', 3),
    (requests.exceptions.ChunkedEncodingError('secret'), 'SSI_BODY_INCOMPLETE', 1),
    (requests.exceptions.ContentDecodingError('secret'), 'SSI_BODY_INCOMPLETE', 1),
])
def test_failed_or_truncated_response(exc, code, attempts):
    a, session = adapter()
    session.responses = [response({'accessToken':'synthetic-token'})] + [exc] * (attempts*3)
    report, memory = run(a, write=True)
    assert code in {e['code'] for e in report['errors']} and not memory.writes
    assert len(session.calls) == 1+attempts*3 and 'secret' not in json.dumps(report)


def test_exact_json_decimal_parsing_and_sanitized_raw():
    a, session = adapter()
    body = deepcopy(SAMPLES['HOSE'])
    body[0].update(lotSize='123.456789012345678901', authToken='secret',
                   nested={'password':'secret','safe':'synthetic-api-secret'})
    session.responses[1] = response(body, raw=json.dumps(body).replace('"123.456789012345678901"', '123.456789012345678901').encode())
    snap = a.fetch('symbols')
    row = snap.records[0]
    assert snap.complete and row['lot_size'] == '123.456789012345678901'
    assert row['raw']['lotSize'] == '123.456789012345678901'
    assert 'authToken' not in row['raw'] and row['raw']['nested'] == {'safe':'[REDACTED]'}
    assert 'synthetic-api-secret' not in json.dumps(row)


def test_nonfixed_historical_reference_and_extreme_reduction():
    # Different counts are fine; these observations are not exact requirements.
    ref = {'date': 'test', 'counts': {'HOSE':4,'HNX':3,'UPCOM':4}}
    a, _ = adapter(reference=ref)
    assert a.fetch('symbols').complete
    a, _ = adapter(reference=OWNER_REFERENCE)
    report, memory = run(a, write=True)
    assert not memory.writes and report['status'] == 'FAILED'
    assert 'SOURCE_COUNT_REGRESSION' in {e['code'] for e in report['errors']}
    assert report['source_missing_records'] is None


def test_large_db_drop_blocks_before_missing_classifications():
    a, _ = adapter()
    old = [{'symbol':f'OLD{i}', 'market':'HNX', 'status':'active','intraday_status':'active'} for i in range(20)]
    report, memory = run(a, write=True, rows=old)
    assert report['status'] == 'FAILED' and not memory.writes
    assert report['retention_check']['status'] == 'BLOCKED'
    assert report['source_missing_records'] is None and report['classifications'] == []


@pytest.mark.parametrize('dataset', ['symbols'])
def test_real_adapter_pipeline_dry_write_repeat(dataset):
    a, _ = adapter()
    report, memory = run(a, dataset)
    assert report['status'] == 'OK' and report['planned_inserts'] == 8 and memory.writes == []
    a, _ = adapter()
    report, memory = run(a, dataset, write=True, memory=memory)
    assert report['status'] == 'OK' and report['actual_inserts'] == 8 and report['readback_status'] == 'PASS'
    if dataset == 'symbols':
        assert all(r['status'] == r['intraday_status'] == 'inactive' for r in memory.tables[dataset])
    a, _ = adapter()
    repeat, memory = run(a, dataset, write=True, memory=memory)
    assert repeat['status'] == 'OK' and repeat['unchanged_records'] == 8 and len(memory.writes) == 8


def test_existing_controls_missing_records_and_nulls_preserved():
    old = [dict(symbol='SSI',market='HOSE',name='old',status='inactive',intraday_status='active'),
           dict(symbol='ABSENT',market='HOSE',name='retained',status='active',intraday_status='inactive')]
    a, _ = adapter()
    report, memory = run(a, write=True, rows=old)
    ssi = next(r for r in memory.tables['symbols'] if r['symbol']=='SSI')
    assert report['source_missing_records'] == 1 and ssi['status']=='inactive' and ssi['intraday_status']=='active'
    assert next(r for r in memory.tables['symbols'] if r['symbol']=='ABSENT') == old[1]
    a, _ = adapter()
    old = [dict(symbol='HNXSTOCK',market='HNX',stock_en_name='known English name',listed_share='100000')]
    report, memory = run(a, 'symbols', write=True, rows=old)
    row = next(r for r in memory.tables['symbols'] if r['symbol']=='HNXSTOCK')
    assert row['stock_en_name']=='known English name' and row['listed_share']=='100000'


def test_partial_write_and_readback_safe_rerun():
    a, _ = adapter(); memory = MemoryClient('symbols'); memory.corrupt_readback=True
    report, memory = run(a, write=True, memory=memory)
    assert report['status']=='PARTIAL' and report['actual_inserts']==1 and report['readback_status']=='FAIL'
    memory.corrupt_readback=False; a, _ = adapter()
    report, memory = run(a, write=True, memory=memory)
    assert report['status']=='OK' and report['actual_inserts']==7 and report['unchanged_records']==1


@pytest.mark.parametrize('command', ['sync-master-data','init'])
def test_cli_real_registry_default_source_and_explicit_write(command, monkeypatch, capsys):
    a, _ = adapter()
    monkeypatch.setattr('src.providers.ssi.adapters.master_v3.SSIV3Client', lambda: a.client)
    monkeypatch.setattr('src.providers.ssi.adapters.master_v3.OWNER_REFERENCE', REFERENCE)
    memory = MemoryClient('symbols')
    monkeypatch.setattr('src.ingest.master.sync.MasterStore', lambda: MasterStore(memory))
    assert main([command,'--dataset','symbols']) == 0
    report=json.loads(capsys.readouterr().out)
    assert report['datasets'][0]['data_source']=='ssi_v3' and report['mode']=='DRY_RUN' and not memory.writes
    a, _ = adapter(); monkeypatch.setattr('src.providers.ssi.adapters.master_v3.SSIV3Client', lambda: a.client)
    assert main([command,'--dataset','symbols','--data-source','ssi_v3','--write'])==0
    report=json.loads(capsys.readouterr().out)
    assert report['actual_inserts']==8
    assert main([command,'--dataset','all','--write'])==2


def test_legacy_import_mapper_and_independent_index_capabilities():
    from src.ingest.master.init_symbols import map_security_record
    from src.ingest.master.index_master import sync_indexes, sync_index_components
    assert map_security_record(SAMPLES['HNX'][1])['sec_type']=='Bond'
    assert sync_indexes()['status']=='BLOCKED' and sync_index_components()['status']=='BLOCKED'
    for dataset in ('index_master','index_components'):
        assert not MASTER_REGISTRY.resolve(dataset,'ssi_v3').verified
        assert MASTER_REGISTRY.resolve(dataset,'ssi_v3').status=='BLOCKED'


def test_inspector_verified_descriptive_mapping():
    from scripts.inspectors.ssi_rest.mapping import map_rows
    from src.contracts.registry import get_mapping
    rows = [deepcopy(SAMPLES['HOSE'][0]), deepcopy(SAMPLES['HNX'][1]), deepcopy(SAMPLES['UPCOM'][-1])]
    clean, reports = map_rows('ssi_v3','symbol_list',get_mapping('ssi_v3','symbol_list'),rows,{})
    assert clean[0]['stock_name']=='Chứng khoán mẫu' and clean[0]['market']==clean[0]['exchange']=='HOSE'
    assert clean[1]['security_type']=='Bond' and clean[2]['security_type'] is None
    assert all(not r['errors'] for r in reports) and rows[0]==SAMPLES['HOSE'][0]


def test_retry_after_date_and_invalid_values():
    delay = master_retry_delay(response([],429,headers={'Retry-After':format_datetime(datetime.now(timezone.utc)+timedelta(seconds=10))}),1)
    assert 8 <= delay <= 10
    assert master_retry_delay(response([],429,headers={'Retry-After':'100'}),1) is None
    assert master_retry_delay(response([],429,headers={'Retry-After':'bad'}),1) is None
    assert master_retry_delay(response([],429,headers={'Retry-After':'NaN'}),1) is None


@pytest.mark.parametrize('field,value', [('symbolNameEn',' '), ('lotSize',''), ('listedShare',None),
    ('firstTradingDate',' '), ('lastTradingDate',''), ('maturityDate',None), ('stockType','')])
def test_optional_empty_fields_are_null(field,value):
    row=deepcopy(SAMPLES['HOSE'][0]);row[field]=value
    mapped=map_verified_record('symbols',row)
    target={'symbolNameEn':'stock_en_name','lotSize':'lot_size','listedShare':'listed_share',
            'firstTradingDate':'first_trading_date','lastTradingDate':'last_trading_date',
            'maturityDate':'maturity_date','stockType':'sec_type'}[field]
    assert mapped[target] is None


@pytest.mark.parametrize('value', [[],True,0,None])
def test_nonobject_records_block_without_db_construction(value):
    samples=deepcopy(SAMPLES);samples['HOSE'][0]=value;a,_=adapter(samples)
    cap=replace(MASTER_REGISTRY.resolve('symbols'),factory=lambda:a)
    def no_store(): raise AssertionError('DB constructed on invalid source')
    report=run_master_sync('symbols',write=True,registry=MasterRegistry([cap]),store_factory=no_store)['datasets'][0]
    assert report['stage']=='SOURCE_FETCH' and report['invalid_records']==1
    assert report['errors'][0]['code']=='INVALID_SOURCE_RECORD'


@pytest.mark.parametrize('code,expected', [(401,'SSI_AUTH_FAILED'),(403,'SSI_AUTH_FAILED'),
    (429,'SSI_RATE_LIMIT'),(503,'SSI_API_ERROR')])
def test_api_error_envelopes_are_not_success(code,expected):
    a,session=adapter();session.responses=[response({'accessToken':'synthetic-token'})]+[response({'code':code,'msg':'secret'})]*3
    report,memory=run(a,write=True)
    assert expected in {e['code'] for e in report['errors']} and not memory.writes
    assert 'secret' not in json.dumps(report)


def test_symbol_normalization_long_bond_unknown_type_and_zero():
    row=deepcopy(SAMPLES['HNX'][1]);row.update(symbol=' bond_identifier_12345678901234567890 ',stockType='Warrant-like future type',lotSize=0)
    mapped=map_verified_record('symbols',row)
    assert mapped['symbol']=='BOND_IDENTIFIER_12345678901234567890'
    assert mapped['sec_type']=='Warrant-like future type' and mapped['lot_size']=='0'


def test_source_size_bound_and_numeric_underscore_rejected():
    row=deepcopy(SAMPLES['HOSE'][0]);row['listedShare']='1_000'
    with pytest.raises(Exception,match='INVALID_SOURCE_NUMERIC'):map_verified_record('symbols',row)
    samples=deepcopy(SAMPLES);samples['HOSE']=[samples['HOSE'][0]]*20_001
    a,_=adapter(samples);report,memory=run(a,write=True)
    assert 'SOURCE_BOARD_LIMIT' in {e['code'] for e in report['errors']} and not memory.writes


def test_body_size_limit_before_json_parse():
    client=SSIV3Client(session=Session([response(raw=b' '*(16*1024*1024+1))]));client.token='synthetic-token'
    with pytest.raises(SSIReadError) as exc:client.securities_by_board('HOSE')
    assert exc.value.code=='SSI_BODY_LIMIT'


def test_failure_after_successful_boards_retains_evidence_without_any_write():
    a,session=adapter();session.responses[-1]=response(raw=b'[{')
    report,memory=run(a,write=True)
    assert report['status']=='FAILED' and not memory.writes
    assert [d['status'] for d in report['pagination']['boards']]==['PASS','PASS','FAILED']
    assert report['source_records_received']==5


def test_security_type_distribution_compared_against_existing_db():
    a,_=adapter()
    old=[dict(symbol='SSI',market='HOSE',sec_type='Stock'),dict(symbol='EXISTING',market='HOSE',sec_type='Bond')]
    report,_=run(a,'symbols',rows=old)
    distribution={item['value']:item for item in report['retention_check']['distribution_comparison']}
    assert distribution['Stock']['existing_count']==1 and distribution['Stock']['source_count']==3
    assert distribution['Bond']['existing_count']==1 and distribution['Bond']['source_count']==1
    assert distribution['New instrument class']['change']==1


def test_actual_sdk_numeric_text_casts_on_read_write_and_readback():
    import httpx
    from postgrest import SyncPostgrestClient
    from src.ingest.master.contracts import compare
    calls=[]
    exact='123.456789012345678901'
    def handle(request):
        calls.append(request)
        assert 'lot_size::text' in request.url.params['select']
        assert 'listed_share::text' in request.url.params['select']
        row={'symbol':'SSI','lot_size':exact,'status':'inactive','intraday_status':'inactive'}
        if request.method=='POST':
            payload=json.loads(request.content)
            assert payload['lot_size']==exact
            row.update(payload)
        return httpx.Response(201 if request.method=='POST' else 200,json=[row],headers={'content-range':'0-0/1'})
    http=httpx.Client(base_url='https://master.invalid',transport=httpx.MockTransport(handle))
    client=SyncPostgrestClient('https://master.invalid',http_client=http)
    store=MasterStore(client)
    existing=store.read('symbols')
    assert existing[0]['lot_size']==exact
    plan,_=compare('symbols',[{'symbol':'SSI','lot_size':exact}],[])
    assert store.apply('symbols',plan[0])==1
    store.verify('symbols',plan[0])
    unchanged,_=compare('symbols',[{'symbol':'SSI','lot_size':exact}],existing)
    assert unchanged==[] and len(calls)==3
    http.close()


@pytest.mark.parametrize('auth,expected', [(response({},401),'SSI_AUTH_FAILED'),
    (response({'code':403}),'SSI_AUTH_FAILED'), (response({}),'SSI_AUTH_INVALID_RESPONSE')])
def test_auth_failures_remain_safe_and_distinct(auth,expected):
    a,session=adapter();session.responses=[auth]*3
    report,memory=run(a,write=True)
    assert expected in {e['code'] for e in report['errors']} and not memory.writes
    assert len(session.calls)==3 and all('/auth/token' in call[1] for call in session.calls)


def test_missing_credentials_do_not_request_or_access_database(monkeypatch):
    monkeypatch.setattr('src.config.config.SSI_API_KEY',None)
    a,session=adapter();report,memory=run(a,write=True)
    assert not memory.writes and session.calls==[]
    assert {e['code'] for e in report['errors']} >= {'SSI_CONFIGURATION'}


def test_access_token_echo_redacted_in_raw_or_blocks_mapped_field():
    samples=deepcopy(SAMPLES);samples['HOSE'][0]['unknownNote']='echo synthetic-token'
    a,_=adapter(samples);snap=a.fetch('symbols')
    assert snap.complete and snap.records[0]['raw']['unknownNote']=='echo [REDACTED]'
    samples['HOSE'][0]['stockType']='synthetic-token';a,_=adapter(samples)
    report,memory=run(a,write=True)
    assert not memory.writes and 'synthetic-token' not in json.dumps(report)
    assert 'SOURCE_SECRET_IN_RECORD' in {e['code'] for e in report['errors']}
