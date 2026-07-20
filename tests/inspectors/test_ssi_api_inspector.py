from __future__ import annotations

import requests

from scripts.ssi_api_inspector import inspect
from scripts.ssi_api_inspector.client import InspectorClient, redact
from scripts.ssi_api_inspector.endpoints import ENDPOINTS


class Args:
    symbol = "SSI"
    date = "10/07/2026"
    market = "HOSE"
    exchange = "HOSE"
    index_code = "VNINDEX"
    page_index = 1
    page_size = 10
    ascending = True


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {"dataList": [{"Symbol": "SSI"}], "totalRecord": 1}
        self.text = "x"
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def test_registry_has_nine_official_endpoints():
    assert len(ENDPOINTS) == 9
    assert set(ENDPOINTS) == {
        "access-token", "securities", "securities-details", "index-components", "index-list",
        "daily-ohlc", "intraday-ohlc", "daily-index", "daily-stock-price",
    }


def test_each_endpoint_builds_method_url_and_core_params():
    args = Args()
    assert ENDPOINTS["access-token"].method == "POST"
    assert ENDPOINTS["access-token"].post_json(args)["consumerID"] is not None or "consumerID" in ENDPOINTS["access-token"].post_json(args)
    assert ENDPOINTS["securities"].build_params(args) == {"Market": "HOSE", "PageIndex": 1, "PageSize": 10}
    assert ENDPOINTS["securities-details"].build_params(args)["Symbol"] == "SSI"
    assert ENDPOINTS["index-components"].build_params(args)["IndexCode"] == "VNINDEX"
    assert ENDPOINTS["index-list"].build_params(args)["Exchange"] == "HOSE"
    assert ENDPOINTS["daily-ohlc"].build_params(args)["ascending"] is True
    assert ENDPOINTS["intraday-ohlc"].build_params(args)["resolution"] == 1
    assert ENDPOINTS["daily-index"].build_params(args)["FromDate"] == "10/07/2026"
    assert ENDPOINTS["daily-stock-price"].build_params(args)["Market"] == "HOSE"
    assert all(endpoint.url.startswith("https://") for endpoint in ENDPOINTS.values())


def test_access_token_request_uses_post_json(monkeypatch):
    monkeypatch.setattr("src.config.config.SSI_CONSUMER_ID", "cid")
    monkeypatch.setattr("src.config.config.SSI_CONSUMER_SECRET", "sec")
    session = FakeSession([FakeResponse(body={"data": {"accessToken": "tok"}})])
    client = InspectorClient(session=session)
    client.login()
    method, _url, kwargs = session.calls[0]
    assert method == "POST"
    assert kwargs["json"] == {"consumerID": "cid", "consumerSecret": "sec"}


def test_get_uses_bearer_but_sanitizer_redacts_token_and_header(monkeypatch):
    monkeypatch.setattr("src.config.config.SSI_CONSUMER_ID", "cid")
    monkeypatch.setattr("src.config.config.SSI_CONSUMER_SECRET", "sec")
    session = FakeSession([
        FakeResponse(body={"data": {"accessToken": "secret-token"}}),
        FakeResponse(body={"dataList": [{"Authorization": "Bearer secret-token"}]}),
    ])
    client = InspectorClient(session=session)
    client.request_endpoint(ENDPOINTS["securities"], {"Market": "HOSE"})
    assert session.calls[1][2]["headers"]["Authorization"] == "Bearer secret-token"
    assert "secret-token" not in str(redact({"Authorization": "Bearer secret-token"}))


def test_deep_redaction_top_level_and_nested():
    value = {"token": "abc", "nested": {"accessToken": "def", "rows": [{"consumerSecret": "ghi"}]}}
    safe = redact(value)
    assert safe["token"]["redacted"] is True
    assert safe["nested"]["accessToken"]["length"] == 3
    assert safe["nested"]["rows"][0]["consumerSecret"]["redacted"] is True
    assert "abc" not in str(safe) and "def" not in str(safe) and "ghi" not in str(safe)


def test_default_output_honors_limit(capsys):
    body = {"dataList": [{"a": 1}, {"a": 2}, {"a": 3}]}
    response = type("R", (), {"body": body, "status_code": 200, "elapsed_sec": 0.1, "content_type": "application/json"})()
    inspect.print_report(ENDPOINTS["securities"], {}, response, limit=2, full_json=False)
    out = capsys.readouterr().out
    assert '"a": 1' in out and '"a": 2' in out
    assert '"a": 3' not in out


def test_full_json_is_redacted(capsys):
    body = {"data": {"accessToken": "secret-token", "rows": [{"a": 1}]}}
    response = type("R", (), {"body": body, "status_code": 200, "elapsed_sec": 0.1, "content_type": "application/json"})()
    inspect.print_report(ENDPOINTS["access-token"], {}, response, limit=1, full_json=True)
    out = capsys.readouterr().out
    assert "secret-token" not in out
    assert "redacted" in out


def test_data_locations_and_empty_response(capsys):
    for key in ("data", "dataList", "items"):
        assert inspect._data_location({key: [{"x": 1}]}) == (key, [{"x": 1}])
    assert inspect._data_location({"dataList": []}) == ("dataList", [])
    body = {"dataList": []}
    response = type("R", (), {"body": body, "status_code": 200, "elapsed_sec": 0.1, "content_type": "application/json"})()
    status = inspect.print_report(ENDPOINTS["securities"], {}, response, limit=1, full_json=False)
    assert status == "EMPTY"
    assert "Empty response" in capsys.readouterr().out


def test_401_reauth_retries_once(monkeypatch):
    monkeypatch.setattr("src.config.config.SSI_CONSUMER_ID", "cid")
    monkeypatch.setattr("src.config.config.SSI_CONSUMER_SECRET", "sec")
    session = FakeSession([
        FakeResponse(body={"data": {"accessToken": "tok1"}}),
        FakeResponse(status_code=401, body={"message": "expired"}),
        FakeResponse(body={"data": {"accessToken": "tok2"}}),
        FakeResponse(body={"dataList": [{"Symbol": "SSI"}]}),
    ])
    client = InspectorClient(session=session)
    response = client.request_endpoint(ENDPOINTS["securities"], {"Market": "HOSE"})
    assert response.status_code == 200
    assert len(session.calls) == 4


def test_run_all_summary_exit_code(monkeypatch, capsys):
    class Client:
        def __init__(self, timeout):
            pass
    monkeypatch.setattr(inspect, "InspectorClient", Client)
    monkeypatch.setattr(inspect, "RUN_ALL_ORDER", ["securities", "daily-ohlc"])
    def fake_run_one(_client, name, _args):
        return "PASS" if name == "securities" else "FAILED"
    monkeypatch.setattr(inspect, "run_one", fake_run_one)
    code = inspect.main(["run", "all"])
    out = capsys.readouterr().out
    assert code == 1
    assert "securities: PASS" in out and "daily-ohlc: FAILED" in out


def test_package_has_no_database_imports():
    for path in __import__("pathlib").Path("scripts/ssi_api_inspector").glob("*.py"):
        text = path.read_text()
        assert "SupabaseClient" not in text
        assert ".table(" not in text
        assert ".upsert(" not in text and ".delete(" not in text
