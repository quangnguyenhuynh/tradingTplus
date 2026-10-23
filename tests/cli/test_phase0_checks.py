"""Read-only diagnostics CLI contracts; no external database or SSI requests."""
import json
from datetime import date
from types import SimpleNamespace

import pytest

from scripts.checks import check_ingest as completeness
from scripts.checks import phase0_reconcile_sample as reconcile_cli
from src.quality.validators.phase0 import reconcile_sample


@pytest.mark.parametrize('status,exit_code', [('OK', 0), ('PARTIAL', 1), ('FAILED', 1), ('UNKNOWN', 2),
    ('UNSUPPORTED', 2), ('', 2), (None, 2), (['bad'], 2), ({'bad': True}, 2)])
def test_completeness_exit_status_preserves_full_json(status, exit_code, monkeypatch, capsys):
    seen = []
    report = {'status': status, 'per_symbol': [{'gap_status': 'OBSERVED'}], 'stock_intraday_count': 199,
              'evidence': 'structural checks only'}
    def check(day, **kwargs):
        print('existing progress message')
        seen.append((day, kwargs))
        return report
    monkeypatch.setattr(completeness, 'check_ingest', check)
    assert completeness.main(['--date', '21/10/2026', '--symbols', 'SSI']) == exit_code
    out = capsys.readouterr()
    assert json.loads(out.out) == report
    assert 'existing progress message' in out.err
    assert seen == [('21/10/2026', {'symbols': ['SSI']})]


@pytest.mark.parametrize('report', [None, [], 'unsupported', {}])
def test_indeterminate_result_nonzero_parseable(report, monkeypatch, capsys):
    monkeypatch.setattr(completeness, 'check_ingest', lambda *a, **k: report)
    assert completeness.main(['--date', '2026-10-21']) == 2
    assert json.loads(capsys.readouterr().out) == report


def test_invalid_date_rejected_before_check(monkeypatch, capsys):
    def fail(*a, **kw): raise AssertionError('check ran before validation')
    monkeypatch.setattr(completeness, 'check_ingest', fail)
    assert completeness.main(['--date', '2026-02-30']) == 2
    assert json.loads(capsys.readouterr().out)['error_type'] == 'INVALID_INPUT'


@pytest.mark.parametrize('error,exit_code', [(ValueError('private diagnostic'), 2), (RuntimeError('token=must-not-print'), 1)])
def test_completeness_errors_visible_sanitized_nonzero(error, exit_code, monkeypatch, capsys):
    def fail(*a, **kw): raise error
    monkeypatch.setattr(completeness, 'check_ingest', fail)
    assert completeness.main(['--date', '2026-10-21']) == exit_code
    captured = capsys.readouterr()
    assert str(error) not in captured.out + captured.err
    result = json.loads(captured.out)
    assert result['status'] in {'UNKNOWN', 'FAILED'} and result['read_only'] is True


@pytest.mark.parametrize('status,exit_code', [('PASS', 0), ('WARNING', 0), ('FAIL', 1), ('UNKNOWN', 2)])
@pytest.mark.parametrize('timeframe', ['1m', '1d', '15m', '60m'])
def test_reconciliation_cli_modes_and_exit(status, exit_code, timeframe, monkeypatch, capsys):
    seen = []
    client = object()
    monkeypatch.setattr(reconcile_cli, 'SupabaseClient', lambda: SimpleNamespace(get=lambda: client))
    monkeypatch.setattr(reconcile_cli, 'check_intraday_payload', lambda *a, **kw: {'status': 'UNKNOWN', 'check': 'informational'})
    def reconcile(actual, **kwargs):
        assert actual is client
        seen.append(kwargs)
        return {'status': status, 'read_only': True}
    monkeypatch.setattr(reconcile_cli, 'reconcile_sample', reconcile)
    with pytest.raises(SystemExit) as exc:
        reconcile_cli.main(['--symbol', 'ssi', '--date', '2026-10-21', '--timeframe', timeframe])
    assert exc.value.code == exit_code
    assert seen == [dict(symbol='SSI', trading_date=date(2026, 10, 21), timeframe=timeframe, timestamp=None, tolerance=1e-6)]
    assert json.loads(capsys.readouterr().out)['reconciliation']['status'] == status


@pytest.mark.parametrize('extra', [ ['--date', 'bad'], ['--symbol', 'ALL'], ['--symbol', 'SSI,HPG'],
    ['--timestamp', '2026-10-21T09:15:00'], ['--timestamp', '2026-10-22T02:15:00Z'],
    ['--tolerance', '-1'], ['--tolerance', 'NaN'], ['--tolerance', 'inf']])
def test_reconciliation_invalid_scope_before_client(extra, monkeypatch):
    def fail(*a, **kw): raise AssertionError('DB constructed')
    monkeypatch.setattr(reconcile_cli, 'SupabaseClient', fail)
    with pytest.raises(SystemExit) as exc:
        reconcile_cli.main(['--symbol', 'SSI', '--date', '2026-10-21', '--timeframe', '1m', *extra])
    assert exc.value.code == 2
