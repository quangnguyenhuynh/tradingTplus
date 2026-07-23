import json

import pytest
import requests

from src.ssi import api as api_module


class _Response:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error


def _client(monkeypatch):
    monkeypatch.setattr(api_module.SSIApi, "_login", lambda self: setattr(self, "token", "test"))
    monkeypatch.setattr(api_module.time, "sleep", lambda _seconds: None)
    return api_module.SSIApi()


def test_daily_stock_price_uses_documented_maximum_page_size(monkeypatch):
    client = _client(monkeypatch)
    calls = []

    def fake_get(_url, **kwargs):
        calls.append(kwargs["params"])
        return _Response(
            body={
                "status": "SUCCESS",
                "totalRecord": 1,
                "dataList": [{"Symbol": "FPT", "TradingDate": "17/07/2026"}],
            }
        )

    monkeypatch.setattr(api_module.requests, "get", fake_get)

    item = client.get_daily_price("FPT", "17/07/2026")

    assert item["Symbol"] == "FPT"
    assert calls == [
        {
            "Symbol": "FPT",
            "FromDate": "17/07/2026",
            "ToDate": "17/07/2026",
            "pageIndex": 1,
            "pageSize": 100,
        }
    ]


def test_retryable_http_status_is_retried_with_a_bound(monkeypatch):
    client = _client(monkeypatch)
    responses = [
        _Response(status_code=429, body={"message": "rate limited"}),
        _Response(
            body={
                "status": "SUCCESS",
                "totalRecord": 1,
                "dataList": [{"Symbol": "SSI", "TradingDate": "17/07/2026"}],
            }
        ),
    ]
    monkeypatch.setattr(api_module.requests, "get", lambda *_args, **_kwargs: responses.pop(0))

    assert client.get_daily_price("SSI", "17/07/2026")["Symbol"] == "SSI"
    assert responses == []


def test_network_error_is_retried_with_a_bound(monkeypatch):
    client = _client(monkeypatch)
    calls = 0

    def fake_get(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise requests.ConnectionError("temporary")

    monkeypatch.setattr(api_module.requests, "get", fake_get)

    with pytest.raises(api_module.SSIResponseError, match="network request failed"):
        client.get_daily_price("SSI", "17/07/2026")

    assert calls == api_module.SSI_MAX_ATTEMPTS


def test_401_reauthenticates_once_without_looping(monkeypatch):
    login_count = 0

    def fake_login(self):
        nonlocal login_count
        login_count += 1
        self.token = f"token-{login_count}"

    monkeypatch.setattr(api_module.SSIApi, "_login", fake_login)
    monkeypatch.setattr(api_module.time, "sleep", lambda _seconds: None)
    client = api_module.SSIApi()
    responses = [
        _Response(status_code=401, body={"message": "expired"}),
        _Response(
            body={
                "status": "SUCCESS",
                "totalRecord": 1,
                "dataList": [{"Symbol": "SSI", "TradingDate": "17/07/2026"}],
            }
        ),
    ]
    monkeypatch.setattr(api_module.requests, "get", lambda *_args, **_kwargs: responses.pop(0))

    assert client.get_daily_price("SSI", "17/07/2026")["Symbol"] == "SSI"
    assert login_count == 2


def test_allowed_non_daily_endpoint_keeps_page_size_1000(monkeypatch):
    client = _client(monkeypatch)
    calls = []

    def fake_get(_url, **kwargs):
        calls.append(kwargs["params"])
        return _Response(body={"status": "SUCCESS", "totalRecord": 0, "dataList": []})

    monkeypatch.setattr(api_module.requests, "get", fake_get)

    assert client.get_intraday("SSI", "17/07/2026") == []
    assert calls == [
        {
            "Symbol": "SSI",
            "FromDate": "17/07/2026",
            "ToDate": "17/07/2026",
            "resolution": "1",
            "pageIndex": 1,
            "pageSize": 1000,
        }
    ]


def test_pagination_stops_when_total_record_is_reached(monkeypatch):
    client = _client(monkeypatch)
    calls = []

    def fake_get(_url, **kwargs):
        calls.append(kwargs["params"])
        page_index = kwargs["params"]["pageIndex"]
        items = [{"Symbol": f"SSI{page_index}", "TradingDate": "17/07/2026"}]
        return _Response(body={"status": "SUCCESS", "totalRecord": 2, "dataList": items})

    monkeypatch.setattr(api_module.requests, "get", fake_get)

    items = client.get_daily_prices_for_date("17/07/2026")

    assert [item["Symbol"] for item in items] == ["SSI1", "SSI2"]
    assert [call["pageIndex"] for call in calls] == [1, 2]
    assert all(call["pageSize"] == 100 for call in calls)


def test_retry_logs_do_not_include_authorization_header_or_token(monkeypatch, caplog):
    client = _client(monkeypatch)
    client.token = "secret-token"
    responses = [
        _Response(status_code=500, body={"message": "temporary"}),
        _Response(body={"status": "SUCCESS", "totalRecord": 0, "dataList": []}),
    ]
    monkeypatch.setattr(api_module.requests, "get", lambda *_args, **_kwargs: responses.pop(0))

    with caplog.at_level("WARNING"):
        assert client.get_daily_price("SSI", "17/07/2026") is None

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "secret-token" not in logged
    assert "Authorization" not in logged


def test_empty_first_page_with_positive_total_record_is_retried_then_raised(monkeypatch):
    client = _client(monkeypatch)
    call_count = 0

    def fake_get(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        return _Response(
            body={"status": "SUCCESS", "totalRecord": 1, "dataList": []}
        )

    monkeypatch.setattr(api_module.requests, "get", fake_get)

    with pytest.raises(api_module.SSIEmptyResponseError):
        client.get_daily_price("HPG", "17/07/2026")

    assert call_count == api_module.SSI_MAX_ATTEMPTS


def test_successful_zero_total_record_is_no_data_without_retry(monkeypatch):
    client = _client(monkeypatch)
    call_count = 0

    def fake_get(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        return _Response(
            body={"status": "SUCCESS", "totalRecord": 0, "dataList": []}
        )

    monkeypatch.setattr(api_module.requests, "get", fake_get)

    assert client.get_daily_price("HPG", "19/07/2026") is None
    assert call_count == 1


def test_failed_ssi_envelope_is_not_treated_as_no_data(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        api_module.requests,
        "get",
        lambda *_args, **_kwargs: _Response(
            body={"status": "ERROR", "message": "invalid PageSize", "dataList": []}
        ),
    )

    with pytest.raises(api_module.SSIResponseError, match="invalid PageSize"):
        client.get_daily_price("FPT", "17/07/2026")


def test_non_matching_daily_payload_is_reported_as_mismatch(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        api_module.requests,
        "get",
        lambda *_args, **_kwargs: _Response(
            body={
                "status": "SUCCESS",
                "totalRecord": 1,
                "dataList": [{"Symbol": "HPG", "TradingDate": "17/07/2026"}],
            }
        ),
    )

    with pytest.raises(api_module.SSIDataMismatchError):
        client.get_daily_price("FPT", "17/07/2026")
