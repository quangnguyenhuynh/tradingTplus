"""Owner-copied live excerpts plus clearly synthetic timestamp/paging/value edge cases.

Only the two fixture candle objects and 204 envelope are real supplied evidence.
Every page wrapper, changed candle and metadata error below is synthetic.
"""
import copy
import json
from pathlib import Path

import pytest

from test_intraday_preview import client, Response
from src.contracts.intraday_preview import map_intraday_preview
from src.contracts import map_record
from src.contracts.transforms import intraday_timestamp, TransformError
from src.providers.ssi.adapters.v3 import SSIV3Adapter
from src.providers.ssi.clients.rest_v3 import SSIReadError
from scripts.inspectors.ssi_rest import inspect
from scripts.inspectors.ssi_rest.client import InspectorResponse

EVIDENCE = json.loads(Path('tests/fixtures/data_preview/ssi_v3_intraday_ssi_2026-10-20_owner_samples.json').read_text())


def row(**changes):
    """A modified row is synthetic, even though its starting point is owner evidence."""
    return {**EVIDENCE['raw_candles'][0], **changes}


def mapped(record):
    clean, reports = map_intraday_preview([record], 'SSI', '2026-10-20', '2026-10-20', source='ssi_v3')
    return clean[0], reports[0]


def preview(bodies):
    cli, session = client(bodies)
    return SSIV3Adapter(cli).preview_intraday('SSI', '2026-10-20'), session


def test_copied_real_candles_and_terminal_replay_without_inventing_226_rows():
    before = copy.deepcopy(EVIDENCE)
    # Array wrappers are synthetic; the original success-page envelope was not supplied.
    bodies = [{'data': [r]} for r in EVIDENCE['raw_candles']] + [EVIDENCE['terminal_envelope']]
    result, session = preview(bodies)
    assert len(session.calls) == 3
    assert result.raw == EVIDENCE['raw_candles'] and EVIDENCE == before
    assert len(result.clean) == result.mapping_report['records_mapped'] == 2
    assert result.mapping_report['records_rejected'] == 0
    assert [r['time'] for r in result.clean] == ['2026-10-20T07:45:00Z', '2026-10-20T07:29:00Z']
    assert [r['value'] for r in result.clean] == [52400670000, 2560650000]
    assert all(type(r['value']) is int for r in result.clean)
    report = result.mapping_report
    assert report['pagination_complete'] and report['pagination_termination'] == 'provider_no_content_204'
    assert report['pages_requested'] == report['pages_received'] == 3
    assert report['source_first_received_time'] == '2026/10/20 14:45:00'
    assert report['source_last_received_time'] == '2026/10/20 14:29:00'
    assert report['duplicate_timestamp_count'] == 0 and report['value_source'] == 'ohlc.value'
    assert report['source_value_present_count'] == report['source_value_mapped_count'] == 2
    assert report['source_value_missing_count'] == report['source_value_invalid_count'] == 0
    assert report['source_value_semantics_verified'] is False
    assert report['completeness_status'] == 'UNVERIFIED' and report['production_ready'] is False


def test_dictionary_itself_maps_observed_tradingdate_not_only_inspector():
    r = EVIDENCE['raw_candles'][0]
    result = map_record('ssi_v3', 'stock_intraday', {f'ohlc.{k}': v for k, v in r.items()},
                        {'symbol': 'SSI', 'from_date': '2026-10-20', 'to_date': '2026-10-20'})
    assert result.candidate['time'] == '2026-10-20T07:45:00Z'
    assert result.candidate['value'] == 52400670000


@pytest.mark.parametrize('stamp,utc', [
    ('2026/10/20 14:45:00.123456', '2026-10-20T07:45:00.123456Z'),
    ('2026-10-20T14:45:00+07:00', '2026-10-20T07:45:00Z'),
    ('2026-10-20T07:45:00Z', '2026-10-20T07:45:00Z'),
    ('2026-10-19T23:45:00Z', '2026-10-19T23:45:00Z'),  # Vietnam date is October 20
])
def test_source_specific_market_local_and_explicit_aware_instants(stamp, utc):
    clean, _ = mapped(row(tradingDate=stamp))
    assert clean['time'] == utc


@pytest.mark.parametrize('stamp', ['2026/02/30 14:45:00', '14:45:00', '2026/10/20',
                                  '2026-10-20 14:45:00', '2026/10/19 14:45:00',
                                  '2026/10/20 24:00:00', None, ''])
def test_bad_incomplete_unobserved_naive_and_outside_dates_reject(stamp):
    clean, report = mapped(row(tradingDate=stamp))
    assert clean is None and any(e.get('field') == 'time' for e in report['errors'])


def test_missing_tradingdate_without_legacy_aware_alias_rejects():
    r = row();r.pop('tradingDate')
    clean, report = mapped(r)
    assert clean is None and 'time' in report['missing_required']


def test_market_local_interpretation_is_not_added_to_generic_transform():
    with pytest.raises(TransformError, match='UNVERIFIED'):
        intraday_timestamp('2026/10/20 14:45:00', {})


def test_source_symbol_and_separate_date_identity_remain_checked():
    for r in (row(symbol='HPG'), row(date='2026-10-19')):
        clean, report = mapped(r)
        assert clean is None and any(e['code'] == 'IDENTITY_MISMATCH' for e in report['errors'])


@pytest.mark.parametrize('code', [204, '204'])
def test_first_page_no_content_is_empty_and_preserved(code):
    body = {'code': code, 'msg': 'No Content'}
    result, _ = preview([body])
    report = result.mapping_report
    assert result.raw == result.clean == [] and report['status'] == 'EMPTY'
    assert report['pagination_complete'] and report['raw_pages'] == [body]
    assert report['pagination_termination'] == 'provider_no_content_204'


@pytest.mark.parametrize('extra', [
    {'data': [row()]}, {'result': {'items': [row()]}}, {'data': 'malformed'},
    {'symbol': 'SSI'}, {'success': False}, {'error': 'failed'}, {'status': 'failed'},
    {'errorCode': 400}, {'msg': 'Not found'}, {'message': 'Invalid token'}, {'code': 204.0},
])
def test_conflicting_or_malformed_204_is_not_no_data(extra):
    body = {'code': 204, 'msg': 'No Content', **extra}
    result, _ = preview([body])
    assert result.mapping_report['status'] == 'FAILED'
    assert not result.mapping_report['pagination_complete']
    assert result.mapping_report['raw_pages'] == [body]


def test_no_content_retains_count_consistency_checks():
    for first, terminal in [
        ({'data': [row()], 'totalRecord': 2}, EVIDENCE['terminal_envelope']),
        ({'data': [row()], 'pagesCount': 3}, EVIDENCE['terminal_envelope']),
        ({'data': [row()], 'totalRecord': 1}, {**EVIDENCE['terminal_envelope'], 'totalRecord': 2}),
        ({'data': [row()]}, {**EVIDENCE['terminal_envelope'], 'pageIndex': 9}),
    ]:
        result, _ = preview([first, terminal])
        assert result.mapping_report['status'] == 'FAILED'
        assert not result.mapping_report['pagination_complete']


@pytest.mark.parametrize('body', [Response({'code': 400}, 400), Response({'code': 401}, 401),
                                Response({'code': 403}, 403), Response({'code': 500}, 500),
                                {'code': 404, 'msg': 'Not Found'}, {'code': 204},
                                {'code': 200, 'msg': 'No Content'}])
def test_other_failures_never_become_204_success(body):
    result, _ = preview([body])
    assert result.mapping_report['status'] == 'FAILED' and not result.mapping_report['pagination_complete']


def test_204_does_not_change_daily_or_index_request_behavior():
    cli, _ = client([EVIDENCE['terminal_envelope']])
    with pytest.raises(SSIReadError):cli.securities_summary('SSI', '2026-10-20')
    cli, _ = client([EVIDENCE['terminal_envelope']])
    with pytest.raises(SSIReadError):cli.index_summary('VNINDEX', '2026-10-20')


@pytest.mark.parametrize('value,expected', [
    ('52400670000', 52400670000), ('9007199254740993', 9007199254740993),
    (str(2**63-1), 2**63-1), (2**63-1, 2**63-1), ('0', 0), (0, 0),
    ('1994000.000', 1994000), ('1.994e6', 1994000),
])
def test_source_value_exact_integer_without_float(value, expected):
    clean, report = mapped(row(value=value))
    assert clean['value'] == expected and type(clean['value']) is int
    assert report['source_value_status'] == 'MAPPED'


def test_synthetic_non_equivalence_source_value_always_wins(monkeypatch):
    def fail(*_a, **_k):pytest.fail('estimator must not run in SSI v3 preview')
    monkeypatch.setattr('src.intraday_value.calculate_trade_value', fail)
    r = row(close='19950', volume='100', value='1994000')
    before = copy.deepcopy(r)
    clean, _ = mapped(r)
    assert clean['value'] == 1994000 != 19950 * 100 and r == before


@pytest.mark.parametrize('missing', [None, ''])
def test_null_value_diagnostic_without_fallback_or_zero(missing, monkeypatch):
    def fail(*_a, **_k):pytest.fail('no calculated fallback')
    monkeypatch.setattr('src.intraday_value.calculate_trade_value', fail)
    clean, report = mapped(row(value=missing))
    assert clean['value'] is None and report['source_value_status'] == 'MISSING'
    assert report['warnings'][0]['code'] == 'SOURCE_VALUE_MISSING'


def test_absent_value_keeps_nullable_contract():
    r = row();r.pop('value')
    clean, report = mapped(r)
    assert clean['value'] is None and 'value' in report['missing_optional']


@pytest.mark.parametrize('bad', ['NaN', 'Infinity', '-1', '1.5', str(2**63),
                                 'abc', True, 0.0, 9007199254740992.0, {}, [], '1_000'])
def test_invalid_source_value_rejects_without_repair(bad):
    r = row(value=bad);before=copy.deepcopy(r)
    clean, report = mapped(r)
    assert clean is None and report['source_value_status'] == 'INVALID'
    assert any(e.get('field') == 'value' for e in report['errors']) and r == before


def test_missing_and_invalid_value_counts_distinct_from_present_and_mapped():
    result, _ = preview([{'data': [row(value=0), row(value=None), row(value='bad')]}, EVIDENCE['terminal_envelope']])
    r = result.mapping_report
    assert r['source_value_present_count'] == 2 and r['source_value_missing_count'] == 1
    assert r['source_value_invalid_count'] == 1 and r['source_value_mapped_count'] == 1
    assert r['source_value_numeric_valid_count'] == 1 and r['source_value_semantics_verified'] is False


@pytest.mark.parametrize('flag', ['--show-mapping', '--full-json'])
def test_existing_inspector_commands_replay_supplied_rows_and_204(flag, monkeypatch, capsys):
    from src.database.client import SupabaseClient
    def fail(*_a, **_k):pytest.fail('preview accessed database')
    monkeypatch.setattr(SupabaseClient, '__new__', fail)
    class Inspector:
        token=None
        def __init__(self,*_a,**_k):pass
        def request_endpoint(self, endpoint, params):
            body = {'data': EVIDENCE['raw_candles']} if params['pageIndex'] == 1 else EVIDENCE['terminal_envelope']
            return InspectorResponse(200,.1,'application/json',body,'json','json',endpoint.url,{})
    monkeypatch.setattr(inspect,'InspectorClient',Inspector)
    assert inspect.main(['run','stock-intraday','--symbol','SSI','--date','2026-10-20',flag]) == 0
    output=capsys.readouterr().out
    assert 'provider_no_content_204' in output and '52400670000' in output
    assert '"records_mapped": 2' in output and '"records_rejected": 0' in output
    assert 'ohlc.tradingDate' in output and 'ohlc.value' in output
    assert 'estimated round' not in output and 'completeness: UNVERIFIED' in output


def test_market_local_transform_cannot_leak_to_legacy_time_alias_direct_mapper():
    r = row();r['time']=r.pop('tradingDate')
    result=map_record('ssi_v3','stock_intraday',{f'ohlc.{k}':v for k,v in r.items()}, {'symbol':'SSI'})
    assert result.candidate is None
    assert any('UNVERIFIED_TIMESTAMP' in e.get('message','') for e in result.report['errors'])
