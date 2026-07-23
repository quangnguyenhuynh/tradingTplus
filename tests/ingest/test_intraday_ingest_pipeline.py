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


def test_intraday_scope_deduplicates_and_does_not_use_master_fallback(monkeypatch):
    db = _DB()
    db.get_symbols = lambda: (_ for _ in ()).throw(AssertionError("must not read master"))
    monkeypatch.setattr(intraday_ingest, 'SupabaseClient', lambda: db)
    monkeypatch.setattr(intraday_ingest, 'SSIApi', lambda: object())
    calls = []
    monkeypatch.setattr(intraday_ingest, 'fetch_intraday_for_symbol_with_clients', lambda ssi, db_arg, symbol, date, daily_context=None: calls.append(symbol) or {'status': 'OK', 'candles_received': 1, 'candles_valid': 1, 'candles_rejected': 0})
    summary = intraday_ingest.run_intraday_ingest('10/07/2026', symbols=['ssi', ' SSI ', 'hpg'])
    assert calls == ['SSI', 'HPG']
    assert db.context_calls == [('SSI', '2026-07-10'), ('HPG', '2026-07-10')]
    assert summary['symbols'] == ['SSI', 'HPG']


def test_intraday_explicit_empty_scope_is_invalid(monkeypatch):
    db = _DB()
    monkeypatch.setattr(intraday_ingest, 'SupabaseClient', lambda: db)
    import pytest
    with pytest.raises(ValueError):
        intraday_ingest.run_intraday_ingest('10/07/2026', symbols=[])


def test_intraday_calls_only_intraday_endpoint_once_per_symbol(monkeypatch):
    class FailFastSSI:
        def __init__(self):
            self.calls = []

        def get_intraday(self, symbol, date):
            self.calls.append((symbol, date))
            return []

        def _forbidden(self, *args, **kwargs):
            raise AssertionError("intraday ingest called a non-intraday SSI endpoint")

        get_daily_price = _forbidden
        get_daily_prices_for_date = _forbidden
        get_daily_index = _forbidden
        get_index_list = _forbidden
        get_index_components = _forbidden

    db = _DB()
    ssi = FailFastSSI()
    monkeypatch.setattr(intraday_ingest, 'SupabaseClient', lambda: db)
    monkeypatch.setattr(intraday_ingest, 'SSIApi', lambda: ssi)

    def fetch(client, db_arg, symbol, date, daily_context=None):
        client.get_intraday(symbol, date)
        return {'status': 'OK', 'candles_received': 1, 'candles_valid': 1, 'candles_rejected': 0}

    monkeypatch.setattr(intraday_ingest, 'fetch_intraday_for_symbol_with_clients', fetch)
    summary = intraday_ingest.run_intraday_ingest('10/07/2026', symbols=['SSI', 'HPG'])

    assert ssi.calls == [('SSI', '10/07/2026'), ('HPG', '10/07/2026')]
    assert db.context_calls == [('SSI', '2026-07-10'), ('HPG', '2026-07-10')]
    assert summary['status'] == 'OK'
