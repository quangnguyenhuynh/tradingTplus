import importlib.util
from pathlib import Path

import main
from src.pipeline import eod, intraday


def test_main_without_command_returns_invalid_arguments(capsys):
    assert main.main([]) == 2
    assert "usage:" in capsys.readouterr().err


def test_main_invalid_command_returns_invalid_arguments(capsys):
    assert main.main(["unknown"]) == 2
    assert "invalid choice" in capsys.readouterr().err


def test_daily_with_date_calls_pipeline(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "daily_run", lambda date: (captured.setdefault("date", date), {"status": "OK"})[1])
    assert main.main(["daily", "10/07/2026"]) == 0
    assert captured["date"] == "10/07/2026"


def test_daily_without_date_calls_pipeline(monkeypatch):
    captured = {"called": False}
    monkeypatch.setattr(main, "daily_run", lambda date: captured.update(called=True, date=date) or {"status": "OK"})
    assert main.main(["daily"]) == 0
    assert captured == {"called": True, "date": None}


def test_eod_command_calls_existing_pipeline(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "run_eod_pipeline", lambda date: (captured.setdefault("date", date), {"status": "OK"})[1])
    assert main.main(["eod", "10/07/2026"]) == 0
    assert captured["date"] == "10/07/2026"


def test_eod_default_timeframes_include_1d():
    assert "1d" in eod.DEFAULT_EOD_TIMEFRAMES


def test_intraday_does_not_call_daily_ingest(monkeypatch):
    monkeypatch.setattr(intraday, "run_feature_engine_with_summary", lambda **kwargs: {"status": "OK", "total_records": 3, "errors": []})
    summary = intraday.run_intraday_pipeline(symbols=["SSI"])
    assert summary["status"] == "OK"
    assert summary["total_records"] == 3
    assert "legacy feature alias" in summary["legacy_warning"]


def test_scripts_import_without_running():
    for path in [
        "scripts/run_features.py",
        "scripts/check_ingest.py",
        "scripts/eod_dry_run.py",
        "scripts/fetch_one_day.py",
        "scripts/snapshot_orderbook.py",
        "scripts/snapshot_stream.py",
    ]:
        spec = importlib.util.spec_from_file_location(Path(path).stem + "_import_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert hasattr(module, "main")


def test_fetch_one_day_default_is_dry_run():
    import scripts.fetch_one_day as script
    parser_source = Path(script.__file__).read_text()
    assert "default=True" in parser_source
    assert "--write" in parser_source


def test_main_has_no_old_debug_commands():
    source = Path("main.py").read_text()
    for old in ["check-ingest", "eod-dry-run", "snapshot-orderbook", "snapshot-stream", '"test"', '"backfill"']:
        assert old not in source
