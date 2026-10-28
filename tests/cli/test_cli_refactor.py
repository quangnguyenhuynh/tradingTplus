import src.cli.features as cli_features
import src.cli.streaming as cli_streaming
import src.cli.stock as cli_stock
import src.cli.maintenance as cli_maintenance
import importlib.util
from pathlib import Path

import src.cli as main
import pytest
import src.ingest.workflows.stock_eod as stock_eod


def test_main_without_command_returns_invalid_arguments(capsys):
    assert main.main([]) == 2
    assert "usage:" in capsys.readouterr().err


def test_main_invalid_command_returns_invalid_arguments(capsys):
    assert main.main(["unknown"]) == 2
    assert "invalid choice" in capsys.readouterr().err


def test_daily_with_date_calls_pipeline(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli_stock, "run_stock_eod_pipeline", lambda date, symbols=None: (captured.update(date=date, symbols=symbols), {"status": "OK"})[1])
    assert main.main(["stock-eod", "10/07/2026"]) == 0
    assert captured["date"] == "10/07/2026"
    assert captured["symbols"] is None
    assert captured.get("symbols") is None


def test_daily_without_date_calls_pipeline(monkeypatch):
    captured = {"called": False}
    monkeypatch.setattr(cli_stock, "run_stock_eod_pipeline", lambda date, symbols=None: captured.update(called=True, date=date, symbols=symbols) or {"status": "OK"})
    assert main.main(["stock-eod"]) == 0
    assert captured == {"called": True, "date": None, "symbols": None}


def test_stock_eod_command_calls_pipeline(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli_stock, "run_stock_eod_pipeline", lambda date, symbols=None: (captured.update(date=date, symbols=symbols), {"status": "OK"})[1])
    assert main.main(["stock-eod", "10/07/2026"]) == 0
    assert captured["date"] == "10/07/2026"



def test_stock_eod_help_has_no_indexes(capsys):
    with pytest.raises(SystemExit) as exc:
        main.build_parser().parse_args(["stock-eod", "--help"])
    assert exc.value.code == 0
    assert "--indexes" not in capsys.readouterr().out



def test_old_eod_command_is_not_registered():
    assert main.main(["eod"]) == 2


@pytest.mark.parametrize("dataset", ["stock-daily", "stock-intraday", "index-daily"])
def test_data_preview_command_is_not_registered(dataset, capsys):
    assert main.main(["data-preview", dataset]) == 2
    assert "invalid choice" in capsys.readouterr().err


def test_production_help_has_no_data_preview(capsys):
    assert main.main(["--help"]) == 0
    assert "data-preview" not in capsys.readouterr().out
    assert not hasattr(main, "run_preview") and not hasattr(main, "render_preview")


def test_legacy_intraday_feature_alias_is_not_registered():
    assert main.main(["intraday"]) == 2


def test_scripts_import_without_running():
    for path in [
        "scripts/previews/run_features.py",
        "scripts/checks/check_ingest.py",
        "scripts/checks/check_supabase.py",
        "scripts/previews/eod_dry_run.py",
        "scripts/maintenance/fetch_one_day.py",
        "scripts/capture/snapshot_orderbook.py",
        "scripts/capture/snapshot_stream.py",
    ]:
        spec = importlib.util.spec_from_file_location(Path(path).stem + "_import_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert hasattr(module, "main")


def test_fetch_one_day_default_is_dry_run():
    import scripts.maintenance.fetch_one_day as script
    parser_source = Path(script.__file__).read_text()
    assert "default=True" in parser_source
    assert "--write" in parser_source


def test_main_has_no_old_debug_commands():
    source = Path("main.py").read_text()
    for old in ["check-ingest", "eod-dry-run", "snapshot-orderbook", "snapshot-stream", '"test"']:
        assert old not in source




@pytest.mark.parametrize(
    ("command", "runner_name"),
    [("stock-eod-backfill", "run_daily_backfill_pipeline")],
)
def test_split_backfill_cli_passes_dates_and_normalized_symbols(monkeypatch, command, runner_name):
    captured = {}
    monkeypatch.setattr(cli_maintenance, runner_name, lambda start, end, symbols=None: captured.update(start=start, end=end, symbols=symbols) or {"status": "OK"})
    assert main.main([command, "--from", "10/07/2026", "--to", "14/07/2026", "--symbols", "ssi", " HPG ", "SSI"]) == 0
    assert captured == {"start": "10/07/2026", "end": "14/07/2026", "symbols": ["SSI", "HPG"]}


@pytest.mark.parametrize(
    ("command", "runner_name"),
    [("stock-eod-backfill", "run_daily_backfill_pipeline")],
)
def test_split_backfill_cli_aliases_and_status_exit_codes(monkeypatch, command, runner_name):
    captured = {}
    monkeypatch.setattr(cli_maintenance, runner_name, lambda start, end, symbols=None: captured.update(start=start, end=end) or {"status": "PARTIAL"})
    assert main.main([command, "--from-date", "10/07/2026", "--to-date", "10/07/2026"]) == 0
    assert captured == {"start": "10/07/2026", "end": "10/07/2026"}
    monkeypatch.setattr(cli_maintenance, runner_name, lambda *args, **kwargs: {"status": "FAILED"})
    assert main.main([command, "--from", "10/07/2026", "--to", "10/07/2026"]) == 1




def test_backfill_cli_requires_both_dates(capsys):
    assert main.main(["backfill", "--from", "10/07/2026"]) == 2
    assert "required" in capsys.readouterr().err


def test_backfill_cli_failed_summary_returns_one(monkeypatch):
    monkeypatch.setattr(cli_maintenance, "run_backfill_pipeline", lambda start, end, symbols=None: {"status": "FAILED"})
    assert main.main(["backfill", "--from", "10/07/2026", "--to", "10/07/2026"]) == 1















def test_daily_cli_normalizes_and_deduplicates_symbols(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli_stock, "run_stock_eod_pipeline", lambda date, symbols=None: captured.update(date=date, symbols=symbols) or {"status": "OK"})
    assert main.main(["stock-eod", "10/07/2026", "--symbols", "ssi", " HPG ", "SSI"]) == 0
    assert captured["symbols"] == ["SSI", "HPG"]


def test_stock_eod_cli_passes_symbols(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli_stock, "run_stock_eod_pipeline", lambda date, symbols=None: captured.update(date=date, symbols=symbols) or {"status": "OK"})
    assert main.main(["stock-eod", "10/07/2026", "--symbols", "ssi", "HPG"]) == 0
    assert captured["symbols"] == ["SSI", "HPG"]




def test_ingest_commands_reject_symbols_flag_without_values():
    commands = [
        ["stock-eod", "10/07/2026", "--symbols"],
        ["intraday-ingest", "10/07/2026", "--symbols"],
        ["stock-eod", "10/07/2026", "--symbols"],
        ["backfill", "--from", "10/07/2026", "--to", "14/07/2026", "--symbols"],
        ["stock-eod-backfill", "--from", "10/07/2026", "--to", "14/07/2026", "--symbols"],
        ["backfill-intraday", "--from", "10/07/2026", "--to", "14/07/2026", "--symbols"],
    ]
    assert [main.main(command) for command in commands] == [2, 2, 2, 2, 2, 2]


def test_features_daily_routes_source_specific_runner(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli_features, 'run_daily_features_with_summary', lambda **kwargs: captured.update(kwargs) or {'status': 'OK'})
    assert main.main(['features-daily', '--mode', 'incremental', '--date', '10/07/2026', '--symbols', 'ssi']) == 0
    assert captured == {'symbols': ['SSI'], 'mode': 'incremental', 'target_date': '10/07/2026'}


def test_features_intraday_routes_and_rejects_daily(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli_features, 'run_intraday_features_with_summary', lambda **kwargs: captured.update(kwargs) or {'status': 'OK'})
    assert main.main(['features-intraday', '--date', '10/07/2026', '--symbols', 'ssi', '--timeframes', '15m', '--as-of', '14:30']) == 0
    assert captured['timeframes'] == ('15m',) and captured['as_of'] == '14:30'
    assert main.main(['features-intraday', '--timeframes', '1d']) == 2




def test_stock_daily_alias_and_explicit_source(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli_stock, "run_stock_eod_pipeline", lambda date, symbols=None, data_source=None: captured.update(date=date, symbols=symbols, data_source=data_source) or {"status": "OK"})
    assert main.main(["stock-eod", "2026-09-08", "--symbols", "ssi", "--data-source", "ssi_v3"]) == 0
    assert captured == {"date": "2026-09-08", "symbols": ["SSI"], "data_source": "ssi_v3"}
