from datetime import date
from src.pipeline import eod


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
    monkeypatch.setattr(eod, 'daily_run', lambda d: calls.append(('daily_run', d)) or {'symbol_count': 3, 'error_count': 0})
    monkeypatch.setattr(eod, 'check_ingest', lambda d: calls.append(('check_ingest', d)) or _good_ingest_summary())
    result = eod.run_eod_pipeline('05/07/2024')
    assert calls == [('daily_run', '05/07/2024'), ('check_ingest', '05/07/2024')]
    assert 'feature_records' not in result
    assert result['status'] == 'OK'


def test_eod_default_weekday_uses_today(monkeypatch):
    monkeypatch.setattr(eod, 'latest_weekday_on_or_before', lambda: date(2026, 7, 13))
    monkeypatch.setattr(eod, 'daily_run', lambda d: {'symbol_count': 1, 'error_count': 0})
    monkeypatch.setattr(eod, 'check_ingest', lambda d: _good_ingest_summary())
    assert eod.run_eod_pipeline(None)['date'] == '13/07/2026'


def test_eod_default_weekend_uses_prior_weekday():
    from src.pipeline.date_utils import latest_weekday_on_or_before
    assert latest_weekday_on_or_before(date(2026, 7, 12)).isoformat() == '2026-07-10'


def test_eod_partial_when_completeness_partial(monkeypatch):
    monkeypatch.setattr(eod, 'daily_run', lambda d: {'symbol_count': 3, 'error_count': 0})
    summary = _good_ingest_summary() | {'missing_intraday_count': 1, 'status': 'PARTIAL'}
    monkeypatch.setattr(eod, 'check_ingest', lambda d: summary)
    result = eod.run_eod_pipeline('05/07/2024')
    assert result['status'] == 'PARTIAL'


def test_eod_failed_when_daily_or_intraday_empty(monkeypatch):
    monkeypatch.setattr(eod, 'daily_run', lambda d: {'symbol_count': 3, 'error_count': 0})
    monkeypatch.setattr(eod, 'check_ingest', lambda d: {'stock_daily_count': 0, 'stock_intraday_count': 0, 'status': 'FAILED'})
    result = eod.run_eod_pipeline('05/07/2024')
    assert result['status'] == 'FAILED'
    assert 'stock_daily_count == 0' in result['failures']
