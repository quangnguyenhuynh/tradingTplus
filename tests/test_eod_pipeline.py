import pytest

from src.pipeline import eod


def _good_ingest_summary():
    return {
        'symbol_count': 3,
        'stock_daily_count': 3,
        'stock_intraday_count': 300,
        'missing_stock_daily_symbols': [],
    }


def test_run_eod_pipeline_calls_steps_in_order(monkeypatch):
    calls = []

    def fake_daily_run(date):
        calls.append(('daily_run', date))
        return {'symbol_count': 3, 'error_count': 0}

    def fake_check_ingest(date):
        calls.append(('check_ingest', date))
        return _good_ingest_summary()

    def fake_run_feature_engine(symbols=None, mode=None, timeframes=None):
        calls.append(('run_feature_engine', symbols, mode, tuple(timeframes)))
        return 42

    monkeypatch.setattr(eod, 'daily_run', fake_daily_run)
    monkeypatch.setattr(eod, 'check_ingest', fake_check_ingest)
    monkeypatch.setattr(eod, 'run_feature_engine', fake_run_feature_engine)

    result = eod.run_eod_pipeline('05/07/2024')

    assert calls == [
        ('daily_run', '05/07/2024'),
        ('check_ingest', '05/07/2024'),
        ('run_feature_engine', None, 'incremental', ('1m', '5m', '15m', '60m', '1d')),
    ]
    assert result['date'] == '05/07/2024'
    assert result['feature_records']['total'] == 42
    assert result['status'] == 'OK'


def test_run_eod_pipeline_passes_optional_feature_filters(monkeypatch):
    captured = {}
    monkeypatch.setattr(eod, 'daily_run', lambda date: {'symbol_count': 2, 'error_count': 0})
    monkeypatch.setattr(eod, 'check_ingest', lambda date: _good_ingest_summary())

    def fake_run_feature_engine(symbols=None, mode=None, timeframes=None):
        captured.update({'symbols': symbols, 'mode': mode, 'timeframes': timeframes})
        return 7

    monkeypatch.setattr(eod, 'run_feature_engine', fake_run_feature_engine)

    result = eod.run_eod_pipeline('05/07/2024', timeframes=['1m'], symbols=['SSI', 'HPG'])

    assert captured == {'symbols': ['SSI', 'HPG'], 'mode': 'incremental', 'timeframes': ('1m',)}
    assert result['status'] == 'OK'


def test_run_eod_pipeline_fails_when_feature_records_zero(monkeypatch):
    calls = []
    monkeypatch.setattr(eod, 'daily_run', lambda date: calls.append('daily_run') or {'symbol_count': 3, 'error_count': 0})
    monkeypatch.setattr(eod, 'check_ingest', lambda date: calls.append('check_ingest') or _good_ingest_summary())
    monkeypatch.setattr(eod, 'run_feature_engine', lambda **kwargs: calls.append('run_feature_engine') or 0)

    with pytest.raises(RuntimeError, match='feature_records == 0'):
        eod.run_eod_pipeline('05/07/2024')

    assert calls == ['daily_run', 'check_ingest', 'run_feature_engine']


def test_run_eod_pipeline_fails_before_features_when_ingest_empty(monkeypatch):
    calls = []
    monkeypatch.setattr(eod, 'daily_run', lambda date: calls.append('daily_run') or {'symbol_count': 3, 'error_count': 0})
    monkeypatch.setattr(eod, 'check_ingest', lambda date: calls.append('check_ingest') or {
        'symbol_count': 3,
        'stock_daily_count': 0,
        'stock_intraday_count': 0,
        'missing_stock_daily_symbols': ['SSI', 'HPG', 'FPT'],
    })
    monkeypatch.setattr(eod, 'run_feature_engine', lambda **kwargs: calls.append('run_feature_engine') or 10)

    with pytest.raises(RuntimeError, match='stock_daily_count == 0'):
        eod.run_eod_pipeline('05/07/2024')

    assert calls == ['daily_run', 'check_ingest']
