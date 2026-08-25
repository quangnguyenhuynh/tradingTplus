from datetime import date
from src.pipeline import eod


def _good_index_summary():
    return {'index_count': 1, 'index_daily_count': 1, 'status': 'OK'}


def _mock_index_steps(monkeypatch, calls=None):
    monkeypatch.setattr(eod, 'run_index_daily_ingest', lambda d, indexes=None: (calls.append(('index_daily', d)) if calls is not None else None) or _good_index_summary())
    monkeypatch.setattr(eod, 'check_index_completeness', lambda d, indexes=None: (calls.append(('index_check', d)) if calls is not None else None) or _good_index_summary())


def _good_ingest_summary():
    return {
        'symbol_count': 3,
        'stock_daily_count': 3,
        'stock_intraday_count': 300,
        'missing_stock_daily_count': 0,
        'missing_intraday_count': 0,
        'incomplete_intraday_count': 0,
        'status': 'OK',
    }


def test_run_eod_pipeline_does_not_call_feature_engine_and_calls_steps(monkeypatch):
    calls = []
    _mock_index_steps(monkeypatch, calls)
    monkeypatch.setattr(eod, 'daily_run', lambda d, symbols=None: calls.append(('daily_run', d)) or {'symbol_count': 3, 'error_count': 0})
    monkeypatch.setattr(eod, 'run_intraday_ingest', lambda d, symbols=None: calls.append(('run_intraday_ingest', d)) or {'symbol_count': 3, 'error_count': 0})
    monkeypatch.setattr(eod, 'check_ingest', lambda d, symbols=None: calls.append(('check_ingest', d)) or _good_ingest_summary())
    result = eod.run_eod_pipeline('05/07/2024')
    assert calls == [('daily_run', '05/07/2024'), ('run_intraday_ingest', '05/07/2024'), ('index_daily', '05/07/2024'), ('check_ingest', '05/07/2024'), ('index_check', '05/07/2024')]
    assert 'feature_records' not in result
    assert result['status'] == 'OK'


def test_eod_default_weekday_uses_today(monkeypatch):
    _mock_index_steps(monkeypatch)
    monkeypatch.setattr(eod, 'latest_weekday_on_or_before', lambda: date(2026, 7, 13))
    monkeypatch.setattr(eod, 'daily_run', lambda d, symbols=None: {'symbol_count': 1, 'error_count': 0})
    monkeypatch.setattr(eod, 'run_intraday_ingest', lambda d, symbols=None: {'symbol_count': 1, 'error_count': 0})
    monkeypatch.setattr(eod, 'check_ingest', lambda d, symbols=None: _good_ingest_summary())
    assert eod.run_eod_pipeline(None)['date'] == '13/07/2026'


def test_eod_default_weekend_uses_prior_weekday():
    from src.pipeline.date_utils import latest_weekday_on_or_before
    assert latest_weekday_on_or_before(date(2026, 7, 12)).isoformat() == '2026-07-10'


def test_eod_partial_when_completeness_partial(monkeypatch):
    _mock_index_steps(monkeypatch)
    monkeypatch.setattr(eod, 'daily_run', lambda d, symbols=None: {'symbol_count': 3, 'error_count': 0})
    summary = _good_ingest_summary() | {'missing_intraday_count': 1, 'status': 'PARTIAL'}
    monkeypatch.setattr(eod, 'run_intraday_ingest', lambda d, symbols=None: {'symbol_count': 3, 'error_count': 0})
    monkeypatch.setattr(eod, 'check_ingest', lambda d, symbols=None: summary)
    result = eod.run_eod_pipeline('05/07/2024')
    assert result['status'] == 'PARTIAL'


def test_eod_failed_when_daily_or_intraday_empty(monkeypatch):
    _mock_index_steps(monkeypatch)
    monkeypatch.setattr(eod, 'daily_run', lambda d, symbols=None: {'symbol_count': 3, 'error_count': 0})
    monkeypatch.setattr(eod, 'run_intraday_ingest', lambda d, symbols=None: {'symbol_count': 3, 'error_count': 0})
    monkeypatch.setattr(eod, 'check_ingest', lambda d, symbols=None: {'stock_daily_count': 0, 'stock_intraday_count': 0, 'status': 'FAILED'})
    result = eod.run_eod_pipeline('05/07/2024')
    assert result['status'] == 'FAILED'
    assert 'stock_daily_count == 0' in result['failures']


def test_eod_passes_one_normalized_scope_to_every_step(monkeypatch, capsys):
    calls = []
    _mock_index_steps(monkeypatch)
    monkeypatch.setattr(eod, 'daily_run', lambda d, symbols=None: calls.append(('daily', symbols)) or {'symbol_count': 2, 'error_count': 0})
    monkeypatch.setattr(eod, 'run_intraday_ingest', lambda d, symbols=None: calls.append(('intraday', symbols)) or {'symbol_count': 2, 'error_count': 0})
    scoped = _good_ingest_summary() | {'symbol_count': 2, 'symbols': ['SSI', 'HPG']}
    monkeypatch.setattr(eod, 'check_ingest', lambda d, symbols=None: calls.append(('check', symbols)) or scoped)
    result = eod.run_eod_pipeline('10/07/2026', symbols=['ssi', ' HPG ', 'SSI'], timeframes=['1d'])
    assert calls == [('daily', ['SSI', 'HPG']), ('intraday', ['SSI', 'HPG']), ('check', ['SSI', 'HPG'])]
    assert result['symbols'] == ['SSI', 'HPG']
    output = capsys.readouterr().out
    assert 'ignores timeframes' in output
    assert 'ignores symbols' not in output
