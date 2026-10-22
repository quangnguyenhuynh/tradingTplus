"""Synthetic protocol/validation cases, NOT captured SSI responses or live evidence.

Values are adversarial calculator inputs extending the existing repository's
naive-time 10.5/100 example. No fabricated payload is represented as SSI evidence.
"""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
import requests

from src.providers.ssi.clients.rest_v3 import SSIV3Client, SSIReadError, IntradayReadError, ohlc_1m_params
from src.providers.ssi.adapters.v3 import SSIV3Adapter
from src.contracts.intraday_preview import map_intraday_preview
from scripts.inspectors.ssi_rest import inspect
from scripts.inspectors.ssi_rest.client import InspectorResponse


def candle(time='2026-09-08T09:15:00+07:00', **changes):
    return {'symbol': 'SSI', 'time': time, 'open': '10.5', 'high': '10.5',
            'low': '10.5', 'close': '10.5', 'volume': '100', 'value': '1050', **changes}


class Response:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status
        self.text = 'not json' if isinstance(body, Exception) else json.dumps(body)

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


class Session:
    def __init__(self, bodies):
        self.bodies, self.calls = list(bodies), []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        result = self.bodies.pop(0)
        if isinstance(result, Exception):
            raise result
        return result if isinstance(result, Response) else Response(result)


def client(bodies, **options):
    session = Session(bodies)
    result = SSIV3Client(session=session, max_attempts=1, **options)
    result.token = 'test-only-token'
    return result, session


def preview(bodies, **options):
    cli, session = client(bodies)
    result = SSIV3Adapter(cli).preview_intraday('SSI', '2026-09-08', **options)
    return result, session


@pytest.mark.parametrize('day', ['08/09/2026', '2026-09-08', '2026/09/08'])
def test_request_dates_and_explicit_1m(day):
    assert ohlc_1m_params('ssi', day, '2026-09-09', page_index=2, page_size=3, ascending=True) == {
        'symbol': 'SSI', 'from': '2026/09/08 00:00:00', 'to': '2026/09/09 23:59:59',
        'timeFrame': '1m', 'pageIndex': 2, 'pageSize': 3, 'ascending': True,
    }


@pytest.mark.parametrize('options', [{'page_index': 0}, {'page_size': -1}, {'page_size': True}, {'ascending': 'yes'}])
def test_bad_request_options_before_io(options):
    with pytest.raises(ValueError):
        ohlc_1m_params('SSI', '2026-09-08', **options)


def test_reversed_range_before_io():
    with pytest.raises(ValueError):
        ohlc_1m_params('SSI', '2026-09-09', '2026-09-08')


def test_short_pages_never_silently_truncate():
    first, second = candle(), candle('2026-09-08T09:16:00+07:00')
    bodies = [{'data': [first]}, {'data': [second]}, {'data': []}]
    before = copy.deepcopy(bodies)
    result, session = preview(bodies, page_size=1000)
    assert len(session.calls) == 3 and result.raw == [first, second]
    assert result.mapping_report['pagination_complete'] is True
    assert result.mapping_report['completeness_status'] == 'UNVERIFIED'
    assert result.mapping_report['status'] == 'PROVISIONAL'
    assert result.mapping_report['raw_pages'] == before and bodies == before
    assert [c[2]['params']['pageIndex'] for c in session.calls] == [1, 2, 3]


def test_total_and_last_page_metadata():
    result, session = preview([{'data': [candle()], 'pagesCount': 1, 'totalRecord': 1, 'pageIndex': 1}])
    assert len(session.calls) == 1 and result.mapping_report['pagination_complete']


@pytest.mark.parametrize('bodies,code', [
    ([{'data': [candle()]}, {'data': [candle()]}], 'PAGINATION_ERROR'),
    ([{'data': [candle()], 'totalRecord': 2}, {'data': []}], 'PAGINATION_ERROR'),
    ([{'data': [], 'pagesCount': 3}], 'PAGINATION_ERROR'),
    ([{'data': [candle()], 'pageIndex': 2}], 'PAGINATION_ERROR'),
    ([{'data': [candle()], 'totalRecord': 3}, {'data': [], 'totalRecord': 4}], 'PAGINATION_ERROR'),
    ([{'data': [candle()], 'pagesCount': 0}], 'PAGINATION_ERROR'),
    ([{'data': [], 'totalRecord': 'bad'}], 'MALFORMED_RESPONSE'),
    ([{'unrecognized': []}], 'MALFORMED_RESPONSE'),
    ([{'data': {}, 'items': 'bad'}], 'MALFORMED_RESPONSE'),
    ([{'data': [], 'items': []}], 'MALFORMED_RESPONSE'),
    ([{'success': False, 'data': []}], 'MALFORMED_RESPONSE'),
    ([{'data': {'code': 400, 'items': []}}], 'MALFORMED_RESPONSE'),
])
def test_pagination_and_structural_failures_are_not_empty_success(bodies, code):
    result, _ = preview(bodies)
    assert result.mapping_report['status'] == 'FAILED'
    assert result.mapping_report['pagination_diagnostics'][0]['code'] == code
    assert result.mapping_report['raw_pages']  # preserve received failed evidence


def test_page_limit_retains_raw_and_mapped_evidence():
    result, session = preview([{'data': [candle()]}], max_pages=1)
    assert len(session.calls) == 1 and result.clean[0]['value'] == 1050
    assert result.mapping_report['status'] == 'FAILED'
    assert result.mapping_report['pagination_diagnostics'][0]['code'] == 'PAGE_LIMIT'


def test_partial_request_failure_preserves_prior_pages():
    result, session = preview([{'data': [candle()]}, Response({'code': 503, 'msg': 'down'}, 503)])
    assert result.mapping_report['status'] == 'FAILED'
    assert len(result.raw) == 1 and len(result.mapping_report['raw_pages']) == 2
    assert len(session.calls) == 2


@pytest.mark.parametrize('body', [Response({'code': 400, 'msg': 'bad'}, 400),
                                Response({'code': 400, 'msg': 'bad'}),
                                Response(ValueError('broken JSON')), requests.Timeout('timeout')])
def test_http_provider_json_and_network_failures_surface(body):
    result, session = preview([body])
    assert result.mapping_report['status'] == 'FAILED'
    assert result.mapping_report['pagination_diagnostics'][0]['code'] == 'REQUEST_FAILED'
    assert len(session.calls) == 1


def test_empty_does_not_claim_holiday_or_completeness():
    result, _ = preview([{'data': []}])
    assert result.raw == result.clean == [] and result.mapping_report['status'] == 'EMPTY'
    assert result.mapping_report['completeness_status'] == 'UNVERIFIED'


def test_error_messages_do_not_leak_config_or_token(monkeypatch):
    monkeypatch.setattr('src.config.config.SSI_API_SECRET', 'private-test-secret')
    result, _ = preview([Response({'msg': 'test-only-token private-test-secret'}, 403)])
    text = json.dumps(result.mapping_report['pagination_diagnostics'])
    assert 'test-only-token' not in text and 'private-test-secret' not in text


def mapped(row):
    clean, reports = map_intraday_preview([row], 'SSI', '2026-09-08', '2026-09-08', source='ssi_v3')
    return clean[0], reports[0]


def test_valid_aware_mapping_no_scaling_source_value_preserved():
    row = candle(value='999999999', refPrice=123)
    before = copy.deepcopy(row)
    clean, report = mapped(row)
    assert clean['time'] == '2026-09-08T02:15:00Z' and clean['timeframe'] == '1m'
    assert clean['open'] == 10.5 and clean['volume'] == 100 and type(clean['volume']) is int
    assert clean['value'] == 999999999  # deliberately synthetic source/formula mismatch
    assert clean['reference_price'] is clean['ceiling_price'] is clean['floor_price'] is None
    assert 'ohlc.value' not in report['unused_source_fields'] and row == before


@pytest.mark.parametrize('time', ['09:15:00', '2026-09-08', '2026/09/08 09:15:00',
                                 '2026-09-08T09:15:00', 'garbage',
                                 '2026-09-07T09:15:00+07:00', '2026-09-08T23:00:00Z'])
def test_invalid_naive_date_only_time_only_out_of_scope_timestamps(time):
    clean, report = mapped(candle(time))
    assert clean is None and report['errors']


@pytest.mark.parametrize('changes', [{'symbol': 'HPG'}, {'tradingDate': '2026-09-07'},
                                     {'tradingDate': '2026-09-09'}, {'timeFrame': '5m'},
                                     {'open': 0}, {'low': 12}, {'high': 9}, {'close': 'NaN'},
                                     {'high': 'inf'}, {'volume': -1}, {'volume': '1.5'},
                                     {'volume': True}, {'volume': str(2**63)},
                                     {'close': 1e308}, {'open': ''}, {'volume': None}])
def test_invalid_identity_ohlcv_and_null_not_repaired(changes):
    row = candle(**changes)
    before = copy.deepcopy(row)
    clean, report = mapped(row)
    assert clean is None and report['errors'] and row == before


def test_partial_null_records_and_missing_optional_remain_observable():
    row = candle()
    row.pop('close')
    clean, report = mapped(row)
    assert clean is None and 'close' in report['missing_optional']
    assert 'reference_price' in report['unsupported_fields']


def test_zero_volume_is_valid_not_missing():
    clean, _ = mapped(candle(volume=0, value=0))
    assert clean['volume'] == clean['value'] == 0


def test_non_object_raw_is_retained_and_rejected():
    result, _ = preview([{'data': [None, candle()]}, {'data': []}])
    assert result.raw[0] is None and result.clean[0] is None
    assert result.mapping_report['records_rejected'] == 1


def test_raw_order_duplicates_sessions_and_lunch_are_reported():
    rows = [candle('2026-09-08T13:00:00+07:00'), candle('2026-09-08T11:29:00+07:00'),
            candle('2026-09-08T11:30:00+07:00'), candle('2026-09-08T12:00:00+07:00'),
            candle('2026-09-08T14:45:00+07:00'), candle('2026-09-08T14:45:00+07:00')]
    result, _ = preview([{'data': rows}, {'data': []}])
    report = result.mapping_report
    assert result.raw == rows and report['duplicate_timestamp_count'] == 1
    assert report['ordering_anomalies'] == 1
    assert report['status'] == 'PARTIAL' and report['validation_status'] == 'FAILED'
    assert any(w['code'] == 'INTRADAY_OUTSIDE_TRADING_SESSION' for w in report['structural_warnings'])
    assert report['canonical_first_received_utc'] == '2026-09-08T06:00:00Z'
    assert report['canonical_min_utc'] == '2026-09-08T04:29:00Z'


def test_missing_intervals_exclude_lunch_and_do_not_join_dates():
    rows = [candle('2026-09-08T11:29:00+07:00'), candle('2026-09-08T13:00:00+07:00'),
            candle('2026-09-08T13:02:00+07:00')]
    result, _ = preview([{'data': rows}, {'data': []}])
    gaps = [w for w in result.mapping_report['structural_warnings'] if w['code'] == 'INTRADAY_MISSING_INTERVAL']
    assert len(gaps) == 1 and gaps[0]['actual_value']['missing_minutes'] == 1


def test_multi_day_scope_uses_each_candles_source_date():
    cli, _ = client([{'data': [candle(), candle('2026-09-09T09:15:00+07:00')]}, {'data': []}])
    result = SSIV3Adapter(cli).preview_intraday('SSI', '2026-09-08', '2026-09-09')
    assert result.mapping_report['records_valid'] == 2
    assert not any(w['code'] == 'INTRADAY_MISSING_INTERVAL' for w in result.mapping_report['structural_warnings'])


def test_time_fraction_is_not_shifted_or_discarded():
    clean, _ = mapped(candle('2026-09-08T02:15:00.123456Z'))
    assert clean['time'] == '2026-09-08T02:15:00.123456Z'


def test_source_date_disagreement_inside_range_rejected():
    clean, report = map_intraday_preview([candle(tradingDate='2026-09-09')], 'SSI', '2026-09-08', '2026-09-09', source='ssi_v3')
    assert clean == [None] and any(e['field'] == 'time' for e in report[0]['errors'])


def test_production_route_and_readiness_stay_disabled():
    from src.providers.ssi.registry import resolve_source, SourceNotReadyError
    with pytest.raises(SourceNotReadyError):
        resolve_source('stock_intraday', 'ssi_v3')
    with pytest.raises(ValueError, match='unsupported'):
        SSIV3Adapter(client([])[0]).fetch('stock_intraday', 'SSI', '2026-09-08')


@pytest.mark.parametrize('flag', ['--show-mapping', '--full-json'])
def test_inspector_downloads_all_pages_limit_only_display(flag, monkeypatch, capsys):
    requests = []
    class Inspector:
        token = 'test-only-token'
        def __init__(self, *_args, **_kwargs):
            pass
        def request_endpoint(self, endpoint, params):
            requests.append(params)
            row = candle(f"2026-09-08T09:{14+params['pageIndex']:02d}:00+07:00")
            body = {'data': [row] if params['pageIndex'] < 3 else []}
            return InspectorResponse(200, .1, 'application/json', body, 'json', 'json', endpoint.url, {})
    monkeypatch.setattr(inspect, 'InspectorClient', Inspector)
    assert inspect.main(['run', 'stock-intraday', '--symbol', 'SSI', '--date', '2026-09-08',
                         '--limit', '1', flag]) == 0
    output = capsys.readouterr().out
    assert len(requests) == 3 and '"records_received": 2' in output
    assert '"value": 1050' in output and 'PROVISIONAL' in output
    if flag == '--full-json':
        assert '2026-09-08T09:16:00+07:00' in output


def test_inspector_partial_preview_returns_nonzero(monkeypatch, capsys):
    class Inspector:
        token = None
        def __init__(self, *_args, **_kwargs):pass
        def request_endpoint(self, endpoint, params):
            return InspectorResponse(200, .1, 'application/json', {'data': [candle()]}, 'json', 'json', endpoint.url, {})
    monkeypatch.setattr(inspect, 'InspectorClient', Inspector)
    assert inspect.main(['run', 'stock-intraday', '--symbol', 'SSI', '--date', '2026-09-08', '--max-pages', '1']) == 1
    assert 'PAGE_LIMIT' in capsys.readouterr().out


def test_preview_import_and_execution_have_no_database_dependency():
    code = r'''
import builtins
old = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.startswith(('src.database', 'src.ingest', 'supabase', 'src.features')):
        raise AssertionError('Forbidden preview dependency: '+name)
    return old(name, *args, **kwargs)
builtins.__import__ = guarded
from src.providers.ssi.adapters.v3 import SSIV3Adapter
from src.providers.ssi.clients.rest_v3 import PageResult
class Client:
    def ohlc_1m(self, *args, **kwargs):return PageResult([], 1, [{'data': []}])
result = SSIV3Adapter(Client()).preview_intraday('SSI', '2026-09-08')
assert result.mapping_report['status']=='EMPTY'
'''
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_reordered_repeated_pages_are_detected():
    a, b = candle(), candle('2026-09-08T09:16:00+07:00')
    result, _ = preview([{'data': [a, b]}, {'data': [b, a]}])
    assert result.mapping_report['status'] == 'FAILED'
    assert 'loop' in result.mapping_report['pagination_diagnostics'][0]['message']


def test_weekend_no_data_is_not_fabricated_as_candles():
    cli, _ = client([{'data': []}])
    result = SSIV3Adapter(cli).preview_intraday('SSI', '2026-09-06')
    assert result.raw == result.clean == []
    assert result.mapping_report['status'] == 'EMPTY'
    assert result.mapping_report['completeness_status'] == 'UNVERIFIED'


def test_explicit_nonfirst_page_is_labeled_suffix_scope():
    result, session = preview([{'data': []}], page_index=2)
    assert session.calls[0][2]['params']['pageIndex'] == 2
    assert result.mapping_report['pagination_scope'] == 'suffix_from_requested_page'
    assert result.mapping_report['completeness_status'] == 'UNVERIFIED'


def test_inspector_auth_failure_reports_failed_preview_not_traceback(monkeypatch, capsys):
    monkeypatch.setattr('src.config.config.SSI_API_KEY', None)
    monkeypatch.setattr('src.config.config.SSI_API_SECRET', None)
    def fail(*_args, **_kwargs):
        pytest.fail('network accessed without credentials')
    monkeypatch.setattr(requests.sessions.Session, 'request', fail)
    assert inspect.main(['run', 'stock-intraday', '--symbol', 'SSI', '--date', '2026-10-19', '--show-mapping']) == 1
    output = capsys.readouterr().out
    assert 'REQUEST_FAILED' in output and 'Missing SSI_API_KEY' in output


def test_full_preview_execution_blocks_database_construction(monkeypatch):
    from src.database.client import SupabaseClient
    def fail(*_args, **_kwargs):
        pytest.fail('database accessed during preview')
    monkeypatch.setattr(SupabaseClient, '__new__', fail)
    result, _ = preview([{'data': [candle()]}, {'data': []}])
    assert result.mapping_report['records_valid'] == 1


def test_client_retries_are_bounded_and_never_fall_back(monkeypatch):
    monkeypatch.setattr('time.sleep', lambda _n: None)
    cli, session = client([Response({}, 503)] * 3)
    cli.max_attempts = 3
    result = SSIV3Adapter(cli).preview_intraday('SSI', '2026-09-08')
    assert result.mapping_report['status'] == 'FAILED' and len(session.calls) == 3
    assert all(call[1] == 'https://api.ssi.com.vn/api/v3/data/ohlc' for call in session.calls)


def test_full_inspector_output_redacts_secrets_without_mutating_raw(monkeypatch, capsys):
    monkeypatch.setattr('src.config.config.SSI_API_SECRET', 'private-test-secret')
    row = candle(note='test-only-token private-test-secret', apiSecret='private-test-secret')
    before = copy.deepcopy(row)
    class Inspector:
        token = 'test-only-token'
        def __init__(self, *_args, **_kwargs):pass
        def request_endpoint(self, endpoint, params):
            body = {'data': [row] if params['pageIndex'] == 1 else []}
            return InspectorResponse(200, .1, 'application/json', body, 'json', 'json', endpoint.url, {})
    monkeypatch.setattr(inspect, 'InspectorClient', Inspector)
    assert inspect.main(['run', 'stock-intraday', '--symbol', 'SSI', '--date', '2026-09-08', '--full-json']) == 0
    output = capsys.readouterr().out
    assert 'test-only-token' not in output and 'private-test-secret' not in output
    assert row == before
