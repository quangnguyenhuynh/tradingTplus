from __future__ import annotations

from argparse import Namespace

import pytest
import requests

from scripts.inspectors.ssi_rest import inspect
from scripts.inspectors.ssi_rest.client import InspectorClient, InspectorError, InspectorResponse, redact, scrub_text
from scripts.inspectors.ssi_rest.endpoints import RUN_ALL_ORDER, ParameterError, V3_ENDPOINTS
from scripts.inspectors.ssi_rest.datasets import DatasetRequest, build_dataset_plan


class FakeResponse:
    def __init__(self, status_code=200, body=None, text=None, headers=None, url="https://api.ssi.com.vn/test"):
        self.status_code = status_code
        self._body = body
        self.text = text if text is not None else ("" if body is None else "json")
        self.headers = headers or {"content-type": "application/json"}
        self.url = url

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def args(**changes):
    values = dict(symbol=None, date=None, from_date=None, to_date=None, board=None,
                  market=None, exchange=None, index_code=None, page_index=1,
                  page_size=20, ascending=None, endpoint="x", limit=3,
                  full_json=False, timeout=30)
    values.update(changes)
    return Namespace(**values)


def response(body, status=200, state="json", text="json"):
    return InspectorResponse(status, .1, "application/json", body, text, state,
                             "https://api.ssi.com.vn/test", {})








def test_v3_params_date_conversion_and_no_v2_names():
    built = V3_ENDPOINTS["securities-summary"].build_params(args(symbol="SSI", from_date="01/09/2026", to_date="2026-09-08"))
    assert built == {"symbol": "SSI", "from": "2026/09/01", "to": "2026/09/08", "pageIndex": 1, "pageSize": 20}
    assert not ({"fromDate", "toDate"} & built.keys())
    assert not ({"Market", "PageIndex", "PageSize", "resolution"} & built.keys())
    ohlc = V3_ENDPOINTS["intraday-ohlc"].build_params(args(symbol="SSI", date="08/09/2026"))
    assert ohlc["timeFrame"] == "1m" and ohlc["from"].endswith("00:00:00") and ohlc["to"].endswith("23:59:59")
    daily = V3_ENDPOINTS["daily-ohlc"].build_params(args(symbol="SSI", date="2026-09-08"))
    assert daily["timeFrame"] == "1d" and daily["from"] == "2026/09/08 00:00:00" and daily["to"] == "2026/09/08 00:00:00"
    assert "timeFrame" not in built
    assert V3_ENDPOINTS["master-data"].build_params(args(date="2026-09-08")) == {
        "from": "2026/09/08", "to": "2026/09/08", "pageIndex": 1, "pageSize": 20}




def test_selector_and_date_exclusivity():
    with pytest.raises(ParameterError, match="exactly one"):
        V3_ENDPOINTS["securities-by-board"].build_params(args(symbol="SSI", board="HOSE"))
    with pytest.raises(ParameterError, match="cannot be used"):
        V3_ENDPOINTS["daily-ohlc"].build_params(args(symbol="SSI", date="08/09/2026", from_date="01/09/2026", to_date="08/09/2026"))
    with pytest.raises(ParameterError, match="accepts --date only"):
        V3_ENDPOINTS["index-summary"].build_params(args(index_code="VNINDEX", from_date="01/09/2026", to_date="08/09/2026"))
    with pytest.raises(ParameterError, match="earlier"):
        V3_ENDPOINTS["master-data"].build_params(args(from_date="08/09/2026", to_date="01/09/2026"))


def test_aliases_build_only_their_selector():
    assert V3_ENDPOINTS["securities"].build_params(args(board="HOSE", symbol="SSI")) == {"board": "HOSE"}
    assert V3_ENDPOINTS["securities-details"].build_params(args(symbol="SSI", board="HOSE")) == {"symbol": "SSI"}
    assert V3_ENDPOINTS["index-components"].build_params(args(index_code="VNINDEX", symbol="SSI")) == {"index": "VNINDEX"}
    assert "symbol" not in V3_ENDPOINTS["master-data"].build_params(args(symbol="SSI", date="08/09/2026"))




def test_bearer_method_params_and_no_redirect(monkeypatch):
    client = InspectorClient("ssi_v3", session=FakeSession([FakeResponse(body={"data": [{"x": 1}]})]))
    client.token = "tok"
    client.request_endpoint(V3_ENDPOINTS["securities-by-board"], {"board": "HOSE"})
    method, url, kwargs = client.session.calls[0]
    assert (method, url) == ("GET", V3_ENDPOINTS["securities-by-board"].url)
    assert kwargs["params"] == {"board": "HOSE"}
    assert kwargs["headers"]["Authorization"] == "Bearer tok"
    assert kwargs["allow_redirects"] is False


def test_array_data_envelope_auth_and_empty_status(capsys):
    assert inspect.print_report("ssi_v3", V3_ENDPOINTS["daily-ohlc"], {}, response([{"x": 1}]), limit=1, full_json=False) == "PASS"
    assert inspect.print_report("ssi_v3", V3_ENDPOINTS["daily-ohlc"], {}, response({"data": []}), limit=1, full_json=False) == "EMPTY"
    assert inspect.print_report("ssi_v3", V3_ENDPOINTS["access-token"], {}, response({"accessToken": "tok"}), limit=1, full_json=False) == "PASS"
    assert "Record count in current response" in capsys.readouterr().out


def test_http_api_errors_empty_non_json_and_malformed_are_failed(capsys):
    endpoint = V3_ENDPOINTS["daily-ohlc"]
    cases = [
        response({"success": False, "message": "bad", "data": []}),
        response({"data": [{"x": 1}]}, status=400),
        response(None, state="empty", text=""),
        response(None, state="non-json", text="<html>bad</html>"),
    ]
    assert all(inspect.print_report("ssi_v3", endpoint, {}, item, limit=1, full_json=True) == "FAILED" for item in cases)
    assert "<html>bad</html>" in capsys.readouterr().out
    session = FakeSession([FakeResponse(body=ValueError("bad json"), text="{broken")])
    parsed = InspectorClient(session=session)._request("GET", "https://api.ssi.com.vn/test", auth=False)
    assert parsed.json_state == "non-json" and parsed.text == "{broken"


@pytest.mark.parametrize("body", [
    {"code": "400", "msg": "invalid timeframe", "data": []},
    {"code": 400, "msg": "invalid timeframe", "data": [{"symbol": "SSI"}]},
    {"code": "400", "msg": "invalid timeframe"},
])
def test_v3_code_msg_api_error_is_failed_and_visible(body, capsys):
    status = inspect.print_report("ssi_v3", V3_ENDPOINTS["daily-ohlc"], {}, response(body), limit=1, full_json=False)
    output = capsys.readouterr().out
    assert status == "FAILED" and "code=400: invalid timeframe" in output


def test_record_code_status_and_msg_do_not_cause_false_api_error():
    body = {"code": 200, "msg": "success", "data": [{"code": 400, "status": "failed", "msg": "record value"}]}
    assert inspect.print_report("ssi_v3", V3_ENDPOINTS["daily-ohlc"], {}, response(body), limit=1, full_json=False) == "PASS"


def test_nested_and_echoed_secret_redaction(monkeypatch):
    monkeypatch.setattr("src.config.config.SSI_API_SECRET", "server-echo-secret")
    value = {"nested": {"apiKey": "abc", "rows": [{"refreshToken": "def"}]}}
    assert "abc" not in str(redact(value)) and "def" not in str(redact(value))
    assert "server-echo-secret" not in scrub_text("error server-echo-secret")


def test_limit_full_json_and_paging_are_distinct(capsys):
    body = {"dataList": [{"a": 1}, {"a": 2}, {"a": 3}], "pageIndex": 2, "pageSize": 3, "totalRecord": 99}
    inspect.print_report("ssi_v3", V3_ENDPOINTS["daily-ohlc"], {}, response(body), limit=1, full_json=False)
    out = capsys.readouterr().out
    assert '"a": 1' in out and '"a": 2' not in out
    assert '"totalRecord": 99' in out and "Record count in current response: 3" in out
    inspect.print_report("ssi_v3", V3_ENDPOINTS["daily-ohlc"], {}, response(body), limit=1, full_json=True)
    assert '"a": 3' in capsys.readouterr().out


def test_401_recovery_is_once(monkeypatch):
    monkeypatch.setattr("src.config.config.SSI_API_KEY", "key")
    monkeypatch.setattr("src.config.config.SSI_API_SECRET", "secret")
    session = FakeSession([
        FakeResponse(body={"accessToken": "tok1"}), FakeResponse(401, {"message": "expired"}),
        FakeResponse(body={"accessToken": "tok2"}), FakeResponse(401, {"message": "still expired"}),
    ])
    result = InspectorClient("ssi_v3", session=session).request_endpoint(V3_ENDPOINTS["index-list"], {})
    assert result.status_code == 401 and len(session.calls) == 4


def test_retry_429_and_5xx_is_bounded(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _n: None)
    session = FakeSession([FakeResponse(429, {"error": "slow"}, headers={"Retry-After": "0"}), FakeResponse(503, {"error": "down"}), FakeResponse(200, {"data": []})])
    result = InspectorClient(session=session, max_attempts=3)._request("GET", "https://api.ssi.com.vn/test", auth=False)
    assert result.status_code == 200 and len(session.calls) == 3


def test_http_400_is_not_retried_and_message_is_visible(capsys):
    session = FakeSession([FakeResponse(400, {"msg": "invalid timeframe"})])
    result = InspectorClient(session=session, max_attempts=3)._request(
        "GET", "https://api.ssi.com.vn/test", auth=False)
    assert len(session.calls) == 1
    assert inspect.print_report("ssi_v3", V3_ENDPOINTS["daily-ohlc"], {}, result,
                                limit=1, full_json=False) == "FAILED"
    assert "invalid timeframe" in capsys.readouterr().out


def test_run_all_continues_summary_and_does_not_duplicate(monkeypatch, capsys):
    class Client:
        def __init__(self, *a, **k): self.token = None
    seen = []
    monkeypatch.setattr(inspect, "InspectorClient", Client)
    monkeypatch.setattr(inspect, "run_one", lambda c, s, n, a: seen.append(n) or ("FAILED" if n == "index-list" else "PASS"))
    code = inspect.main(["run", "all", "--symbol", "SSI", "--board", "HOSE", "--index-code", "VNINDEX", "--date", "08/09/2026"])
    assert code == 1 and seen == RUN_ALL_ORDER["ssi_v3"] and len(seen) == len(set(seen))
    assert "index-list: FAILED" in capsys.readouterr().out


def test_run_all_uses_endpoint_builders(monkeypatch):
    class Client:
        token = "tok"
        def __init__(self, *a, **k): self.calls = []
        def request_endpoint(self, endpoint, params, post_json=None):
            self.calls.append((endpoint.name, params))
            return response({"data": []})
    client = Client()
    monkeypatch.setattr(inspect, "InspectorClient", lambda *a, **k: client)
    code = inspect.main(["run", "all", "--symbol", "SSI", "--board", "HOSE", "--index-code", "VNINDEX", "--date", "08/09/2026"])
    assert code == 0
    calls = dict(client.calls)
    assert calls["securities-summary"]["from"] == "2026/09/08"
    assert calls["daily-ohlc"]["timeFrame"] == "1d"
    assert calls["intraday-ohlc"]["timeFrame"] == "1m"
    assert "symbol" not in calls["master-data"]


def test_unsupported_v3_option_fails_before_network(monkeypatch):
    class Client:
        token = "tok"
        def __init__(self, *a, **k): pass
        def request_endpoint(self, *a, **k): pytest.fail("network called")
    monkeypatch.setattr(inspect, "InspectorClient", Client)
    assert inspect.main(["run", "master-data", "--symbol", "SSI", "--date", "08/09/2026"]) == 1




def test_package_has_no_database_or_trading_write_imports():
    for path in __import__("pathlib").Path("scripts/inspectors/ssi_rest").glob("*.py"):
        text = path.read_text()
        assert "SupabaseClient" not in text and ".table(" not in text
        assert ".upsert(" not in text and ".delete(" not in text
        assert "place_order(" not in text and "TradingApi" not in text


@pytest.mark.parametrize(("cli_name", "source", "endpoint", "selector"), [
    ("stock-daily", "ssi_v3", "securities-summary", ["--symbol", "SSI"]),
    ("stock-intraday", "ssi_v3", "intraday-ohlc", ["--symbol", "SSI"]),
    ("index-daily", "ssi_v3", "index-summary", ["--index-code", "VNINDEX"]),
])
def test_canonical_dataset_routes_v3(cli_name, source, endpoint, selector, monkeypatch, capsys):
    calls = []
    class Client:
        token = None
        def __init__(self, selected, **_kwargs):
            assert selected == source
        def request_endpoint(self, selected_endpoint, params, post_json=None):
            calls.append((selected_endpoint.native_name, params))
            return response({"data": []})
    monkeypatch.setattr(inspect, "InspectorClient", Client)
    argv = ["run", cli_name, *selector, "--date", "2026-09-08", "--data-source", source]
    assert inspect.main(argv) == 0
    assert calls[0][0] == endpoint and len(calls) == 1
    output = capsys.readouterr().out
    assert f"Data source resolved: {source}" in output and "Dataset requested:" in output


def test_canonical_auto_source_uses_registry_preview_order(monkeypatch, capsys):
    class Client:
        token = None
        def __init__(self, source, **_kwargs): assert source == "ssi_v3"
        def request_endpoint(self, endpoint, params, post_json=None): return response({"data": []})
    monkeypatch.setattr(inspect, "InspectorClient", Client)
    assert inspect.main(["run", "stock-daily", "--symbol", "SSI", "--date", "2026-09-08"]) == 0
    output = capsys.readouterr().out
    assert "Data source requested: auto" in output and "ssi_v3 (ready)" in output




def test_v3_index_range_fans_out_with_context_and_cap_before_network():
    request = DatasetRequest("index_daily", None, "VNINDEX", None, "2026-09-01", "2026-09-03", 1, 10)
    plan = build_dataset_plan(request, "ssi_v3")
    assert [item.label for item in plan.requests] == ["2026-09-01", "2026-09-02", "2026-09-03"]
    assert [item.params["tradingDate"] for item in plan.requests] == ["2026/09/01", "2026/09/02", "2026/09/03"]
    too_wide = DatasetRequest("index_daily", None, "VNINDEX", None, "2026-01-01", "2026-04-11", 1, 10)
    with pytest.raises(ParameterError, match="maximum is 100"):
        build_dataset_plan(too_wide, "ssi_v3")


def test_v3_index_partial_failure_continues_and_exits_nonzero(monkeypatch):
    class Client:
        token = None
        def __init__(self, *_args, **_kwargs): self.count = 0
        def request_endpoint(self, endpoint, params, post_json=None):
            self.count += 1
            if self.count == 2: raise InspectorError("one day failed")
            return response({"data": []})
    monkeypatch.setattr(inspect, "InspectorClient", Client)
    assert inspect.main(["run", "index-daily", "--index-code", "VNINDEX",
                         "--from-date", "2026-09-01", "--to-date", "2026-09-03"]) == 1


@pytest.mark.parametrize("argv", [
    ["run", "stock-daily", "--index-code", "VNINDEX", "--date", "2026-09-08"],
    ["run", "index-daily", "--symbol", "SSI", "--date", "2026-09-08"],
    ["run", "stock-intraday", "--symbol", "SSI"],
    ["run", "stock-daily", "--symbol", "SSI", "--date", "bad"],
    ["run", "stock-daily", "--symbol", "SSI", "--board", "HOSE", "--date", "2026-09-08"],
    ["run", "index-daily", "--index-code", "VNINDEX", "--date", "2026-09-08", "--page-size", "20"],
])
def test_bad_canonical_arguments_fail_before_client_or_network(argv, monkeypatch):
    monkeypatch.setattr(inspect, "InspectorClient", lambda *_a, **_k: pytest.fail("client constructed"))
    with pytest.raises(SystemExit) as exc:
        inspect.main(argv)
    assert exc.value.code == 2


@pytest.mark.parametrize(("name", "source", "native", "selector", "expected"), [
    ("symbol-list", "ssi_v3", "securities-by-board", ["--market", "HOSE"], {"board": "HOSE"}),
    ("index-list", "ssi_v3", "index-list", ["--board", "HOSE"], {"board": "HOSE"}),
    ("index-list", "ssi_v3", "index-list", [], {}),
])
def test_catalog_canonical_routing_without_dates(name, source, native, selector, expected,
                                                  monkeypatch, capsys):
    calls = []
    class Client:
        token = None
        def __init__(self, selected, **_kwargs): assert selected == source
        def request_endpoint(self, endpoint, params, post_json=None):
            calls.append((endpoint.native_name, params)); return response({"data": []})
    monkeypatch.setattr(inspect, "InspectorClient", Client)
    assert inspect.main(["run", name, *selector, f"--data-source={source}"]) == 0
    assert calls == [(native, expected)]
    assert "Catalog completeness: unverified" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [
    ["run", "symbol-list"],
    ["run", "symbol-list", "--board", "HOSE", "--date", "2026-09-08"],
    ["run", "index-list", "--symbol", "SSI"],
    ["run", "index-list", "--board", "HOSE", "--exchange", "HNX"],
    ["run", "symbol-list", "--board", "HOSE", "--page-size", "20"],
])
def test_catalog_invalid_options_fail_before_network(argv, monkeypatch):
    monkeypatch.setattr(inspect, "InspectorClient", lambda *_a, **_k: pytest.fail("client constructed"))
    with pytest.raises(SystemExit) as exc:
        inspect.main(argv)
    assert exc.value.code == 2
