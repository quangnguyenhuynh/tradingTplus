import requests
import pytest

from src.pipeline.daily_service import fetch_daily_for_symbol_with_clients
from src.pipeline.intraday_service import fetch_intraday_for_symbol_with_clients
from src.ssi.api import SSIApi, SSIDataMismatchError, SSIEmptyResponseError


def _api() -> SSIApi:
    api = SSIApi.__new__(SSIApi)
    api.token = "test-token"
    return api


class _Response:
    def __init__(self, payload=None, *, text="json", status_code=200):
        self.payload = payload
        self.text = text
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            raise requests.HTTPError(response=response)


def test_daily_stock_price_uses_documented_maximum_page_size(monkeypatch):
    api = _api()
    calls = []

    def fake_get(_url, params):
        calls.append(params)
        return _Response({"dataList": []})

    monkeypatch.setattr(api, "_get_with_retry", fake_get)

    assert api.get_daily_price_items("FPT", "17/07/2026") == []
    assert calls == [{
        "Symbol": "FPT",
        "FromDate": "17/07/2026",
        "ToDate": "17/07/2026",
        "pageIndex": 1,
        "pageSize": 100,
    }]


def test_intraday_page_size_is_not_changed_with_daily_stock_price(monkeypatch):
    api = _api()
    calls = []
    monkeypatch.setattr(
        api,
        "_get_with_retry",
        lambda _url, params: calls.append(params) or _Response({"dataList": []}),
    )

    assert api.get_intraday("HPG", "17/07/2026") == []
    assert calls[0]["pageSize"] == 1000


def test_ssi_pagination_does_not_treat_server_capped_short_page_as_eof(monkeypatch):
    api = _api()
    rows = [{"id": value} for value in range(1205)]
    calls = []

    def fake_get(_url, params):
        calls.append(dict(params))
        start = (params["pageIndex"] - 1) * 500
        return _Response({"dataList": rows[start:start + 500]})

    monkeypatch.setattr(api, "_get_with_retry", fake_get)
    monkeypatch.setattr("src.ssi.api.time.sleep", lambda _seconds: None)

    assert api._get_all_pages("ssi", page_size=1000) == rows
    assert [call["pageIndex"] for call in calls] == [1, 2, 3, 4]
    assert all(call["pageSize"] == 1000 for call in calls)


def test_ssi_pagination_honors_exact_total_and_detects_no_progress(monkeypatch):
    api = _api()
    pages = {
        1: [{"id": 1}, {"id": 2}],
        2: [{"id": 3}, {"id": 4}],
    }
    monkeypatch.setattr(
        api,
        "_get_with_retry",
        lambda _url, params: _Response(
            {"dataList": pages[params["pageIndex"]], "totalRecord": 3}
        ),
    )
    monkeypatch.setattr("src.ssi.api.time.sleep", lambda _seconds: None)
    assert api._get_all_pages("ssi", page_size=1000) == [
        {"id": 1}, {"id": 2}, {"id": 3}
    ]

    monkeypatch.setattr(
        api,
        "_get_with_retry",
        lambda _url, _params: _Response({"dataList": [{"id": 1}]}),
    )
    with pytest.raises(RuntimeError, match="Repeated SSI page"):
        api._get_all_pages("ssi", page_size=1000, sleep_sec=0)


def test_ssi_pagination_rejects_invalid_page_size():
    with pytest.raises(ValueError, match="page_size"):
        _api()._get_all_pages("ssi", page_size=0)


def test_daily_stock_price_rejects_non_matching_rows(monkeypatch):
    api = _api()
    monkeypatch.setattr(
        api,
        "get_daily_price_items",
        lambda _symbol, _date: [{"Symbol": "HPG", "TradingDate": "17/07/2026"}],
    )

    try:
        api.get_daily_price("FPT", "17/07/2026")
    except SSIDataMismatchError:
        pass
    else:
        raise AssertionError("A non-matching DailyStockPrice row must be classified as MISMATCH")


def test_missing_data_list_is_an_empty_response_not_no_data(monkeypatch):
    api = _api()
    monkeypatch.setattr(api, "_get_with_retry", lambda _url, _params: _Response({}))

    try:
        api.get_daily_price_items("FPT", "17/07/2026")
    except SSIEmptyResponseError:
        pass
    else:
        raise AssertionError("A response without a data list must be EMPTY_RESPONSE")


class _DB:
    pass


def test_services_distinguish_empty_response_from_api_error():
    class EmptySSI:
        def get_daily_price(self, _symbol, _date):
            raise SSIEmptyResponseError("empty")

        def get_intraday(self, _symbol, _date):
            raise requests.Timeout("timeout")

    daily = fetch_daily_for_symbol_with_clients(EmptySSI(), _DB(), "FPT", "17/07/2026")
    intraday = fetch_intraday_for_symbol_with_clients(EmptySSI(), _DB(), "FPT", "17/07/2026")

    assert daily["error_type"] == "EMPTY_RESPONSE"
    assert intraday["error_type"] == "API_ERROR"


def test_http_retry_is_bounded_and_does_not_log_authorization(monkeypatch, caplog):
    api = _api()
    calls = []
    monkeypatch.setattr("src.ssi.api.time.sleep", lambda _seconds: None)

    def timeout(*_args, **_kwargs):
        calls.append(1)
        raise requests.Timeout("network timeout")

    monkeypatch.setattr("src.ssi.api.requests.get", timeout)

    try:
        api._get_with_retry("https://ssi.invalid/endpoint", {"Symbol": "FPT"})
    except requests.Timeout:
        pass
    else:
        raise AssertionError("The final SSI request exception must propagate")

    assert len(calls) == 3
    assert "test-token" not in caplog.text
