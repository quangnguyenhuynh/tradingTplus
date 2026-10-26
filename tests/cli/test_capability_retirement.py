"""Retired integrations must fail before API construction, DB access or partial stages."""
import importlib
import json
import socket
import pytest
import requests
from src.cli import main, build_parser
from src.database.client import SupabaseClient
from src.providers.ssi.clients.rest_v3 import SSIV3Client
from src.providers.ssi.capabilities import CapabilityUnavailableError
from src.providers.ssi.registry import DataSourceError, resolve_source

DISABLED_COMMANDS = [
    ["intraday-ingest", "19/10/2026", "--symbols", "SSI"],
    ["backfill", "--from-date", "19/10/2026", "--to-date", "19/10/2026"],
    ["refill", "--symbol", "SSI", "--from", "19/10/2026", "--to", "19/10/2026"],
    ["streaming-ingest", "--symbols", "SSI", "--channels", "quote", "--write"],
]

@pytest.fixture
def no_services(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("network/database service was accessed")
    monkeypatch.setattr(requests.sessions.Session, "request", fail)
    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(SupabaseClient, "__init__", fail)
    monkeypatch.setattr(SSIV3Client, "__init__", fail)


@pytest.mark.parametrize("argv", DISABLED_COMMANDS)
def test_disabled_cli_preserves_parsing_but_never_executes_handler(argv, no_services, capsys, monkeypatch):
    import src.cli as cli
    monkeypatch.setattr(cli, "import_module", lambda *_: (_ for _ in ()).throw(AssertionError("handler loaded")))
    assert build_parser().parse_args(argv).command == argv[0]
    assert main(argv) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "FAILED" and result["error_type"] == "NOT_IMPLEMENTED"


@pytest.mark.parametrize("command", ["stock-eod", "stock-daily", "daily", "index-daily"])
def test_explicit_v2_is_rejected_before_any_service(command, no_services, capsys):
    assert main([command, "19/10/2026", "--data-source", "ssi_v2"]) == 2
    assert "unsupported data source: ssi_v2" in capsys.readouterr().err


@pytest.mark.parametrize("module,function,args", [
    ("src.ingest.workflows.stock_eod", "run_stock_eod_pipeline", ("19/10/2026",)),
    ("src.ingest.stock_daily.daily", "run_daily_ingest", ("19/10/2026",)),
    ("src.ingest.index_daily.index_daily", "run_index_daily_ingest", ("19/10/2026",)),
    ("src.ingest.maintenance.backfill", "run_daily_backfill_pipeline", ("17/10/2026", "18/10/2026")),
    ("src.ingest.index_daily.index_backfill", "run_index_backfill_pipeline", ("17/10/2026", "18/10/2026")),
])
def test_public_ingest_functions_reject_v2_without_services(module, function, args, no_services):
    with pytest.raises(DataSourceError):
        getattr(importlib.import_module(module), function)(*args, data_source="ssi_v2")


@pytest.mark.parametrize("module,argv", [
    ("scripts.capture.snapshot_stream", ["--symbols", "SSI", "--write"]),
    ("scripts.capture.snapshot_orderbook", ["SSI", "--write"]),
    ("scripts.maintenance.fetch_one_day", ["--symbol", "SSI", "--date", "19/10/2026", "--write"]),
    ("scripts.previews.eod_dry_run", ["--date", "19/10/2026"]),
    ("scripts.checks.check_complete_ssi_ingest", ["--date", "19/10/2026", "--write"]),
    ("scripts.inspectors.ssi_streaming.inspect", ["negotiate"]),
    ("scripts.inspectors.ssi_streaming.inspect", ["run", "quote", "--symbols", "SSI"]),
])
def test_disabled_scripts_report_failure_without_services(module, argv, no_services, capsys):
    assert importlib.import_module(module).main(argv) == 1
    assert json.loads(capsys.readouterr().out)["error_type"] == "NOT_IMPLEMENTED"


def test_inspector_rejects_v2_without_services(no_services):
    from scripts.inspectors.ssi_rest.client import InspectorClient, InspectorError
    from scripts.inspectors.ssi_rest.endpoints import registry, ParameterError
    with pytest.raises(InspectorError, match="unsupported data source"):
        InspectorClient("ssi_v2")
    with pytest.raises(ParameterError, match="unsupported data source"):
        registry("ssi_v2")
