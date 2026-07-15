from src.pipeline import intraday_ingest


class _DB:
    def __init__(self):
        self.context_calls = []
    def get_symbols(self):
        return ['SSI', 'hpg']
    def get_stock_daily(self, symbol, trading_date):
        self.context_calls.append((symbol, trading_date))
        return {'symbol': symbol, 'trading_date': trading_date, 'ref_price': 10, 'ceiling_price': 11, 'floor_price': 9, 'close_price': 10, 'total_match_vol': 100}


def test_intraday_ingest_symbol_scope_normalizes_uppercase(monkeypatch):
    db = _DB()
    monkeypatch.setattr(intraday_ingest, 'SupabaseClient', lambda: db)
    monkeypatch.setattr(intraday_ingest, 'SSIApi', lambda: object())
    calls = []
    def fake_fetch(ssi, db_arg, symbol, date, daily_context=None):
        calls.append((symbol, date, daily_context['symbol']))
        return {'status': 'OK', 'candles_received': 1, 'candles_valid': 1, 'candles_rejected': 0}
    monkeypatch.setattr(intraday_ingest, 'fetch_intraday_for_symbol_with_clients', fake_fetch)
    summary = intraday_ingest.run_intraday_ingest('10/07/2026', symbols=['ssi', 'HPG'])
    assert [call[0] for call in calls] == ['SSI', 'HPG']
    assert summary['symbol_count'] == 2
    assert summary['candles_valid'] == 2
    assert summary['status'] == 'OK'


def test_intraday_ingest_missing_daily_context_reports_partial(monkeypatch):
    class MissingDB(_DB):
        def get_stock_daily(self, symbol, trading_date):
            return None
    monkeypatch.setattr(intraday_ingest, 'SupabaseClient', lambda: MissingDB())
    monkeypatch.setattr(intraday_ingest, 'SSIApi', lambda: object())
    monkeypatch.setattr(intraday_ingest, 'fetch_intraday_for_symbol_with_clients', lambda *a, **k: {'status': 'OK', 'candles_received': 1, 'candles_valid': 1, 'candles_rejected': 0})
    summary = intraday_ingest.run_intraday_ingest('10/07/2026', symbols=['SSI'])
    assert summary['daily_context_missing_count'] == 1
    assert summary['daily_context_missing_symbols'] == ['SSI']
    assert summary['status'] == 'PARTIAL'
