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


def test_backfill_cli_calls_pipeline(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        main,
        "run_backfill_pipeline",
        lambda from_date, to_date: captured.update(from_date=from_date, to_date=to_date) or {"status": "PARTIAL"},
    )

    assert main.main(["backfill", "--from", "01/07/2026", "--to", "10/07/2026"]) == 0
    assert captured == {"from_date": "01/07/2026", "to_date": "10/07/2026"}


def test_backfill_cli_aliases_and_failed_exit(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        main,
        "run_backfill_pipeline",
        lambda from_date, to_date: captured.update(from_date=from_date, to_date=to_date) or {"status": "FAILED"},
    )

    assert main.main(["backfill", "--from-date", "01/07/2026", "--to-date", "10/07/2026"]) == 1
    assert captured == {"from_date": "01/07/2026", "to_date": "10/07/2026"}


def test_backfill_cli_requires_explicit_range(capsys):
    assert main.main(["backfill"]) == 2
    assert "required" in capsys.readouterr().err


def test_intraday_ingest_cli_calls_pipeline_with_symbols(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "run_intraday_ingest", lambda date, symbols=None: captured.update(date=date, symbols=symbols) or {"status": "OK"})
    assert main.main(["intraday-ingest", "10/07/2026", "--symbols", "ssi", "HPG"]) == 0
    assert captured == {"date": "10/07/2026", "symbols": ["SSI", "HPG"]}


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
        "scripts/check_supabase.py",
        "scripts/eod_dry_run.py",
        "scripts/fetch_one_day.py",
        "scripts/backfill_sample.py",
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
    for old in ["check-ingest", "eod-dry-run", "snapshot-orderbook", "snapshot-stream", '"test"']:
        assert old not in source


def test_streaming_ingest_cli_is_dry_run_by_default(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "run_streaming_ingest", lambda **kwargs: captured.update(kwargs) or {"status": "EMPTY"})
    assert main.main(["streaming-ingest", "--symbols", "ssi", "--indexes", "vnindex", "--channels", "quote", "index", "--timeout", "1", "--max-messages-per-channel", "1"]) == 0
    assert captured["symbols"] == ["SSI"]
    assert captured["indexes"] == ["VNINDEX"]
    assert captured["write"] is False


def test_streaming_ingest_cli_write_flag(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "run_streaming_ingest", lambda **kwargs: captured.update(kwargs) or {"status": "OK"})
    assert main.main(["streaming-ingest", "--symbols", "SSI", "--channels", "quote", "--write"]) == 0
    assert captured["write"] is True
