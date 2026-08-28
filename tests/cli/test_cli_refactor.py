import importlib.util
from pathlib import Path

import main
import pytest
from src.pipeline import intraday, stock_eod


def test_main_without_command_returns_invalid_arguments(capsys):
    assert main.main([]) == 2
    assert "usage:" in capsys.readouterr().err


def test_main_invalid_command_returns_invalid_arguments(capsys):
    assert main.main(["unknown"]) == 2
    assert "invalid choice" in capsys.readouterr().err


def test_daily_with_date_calls_pipeline(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "daily_run", lambda date, symbols=None: (captured.update(date=date, symbols=symbols), {"status": "OK"})[1])
    assert main.main(["daily", "10/07/2026"]) == 0
    assert captured["date"] == "10/07/2026"
    assert captured["symbols"] is None
    assert captured.get("symbols") is None


def test_daily_without_date_calls_pipeline(monkeypatch):
    captured = {"called": False}
    monkeypatch.setattr(main, "daily_run", lambda date, symbols=None: captured.update(called=True, date=date, symbols=symbols) or {"status": "OK"})
    assert main.main(["daily"]) == 0
    assert captured == {"called": True, "date": None, "symbols": None}


def test_stock_eod_command_calls_pipeline(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "run_stock_eod_pipeline", lambda date, symbols=None: (captured.update(date=date, symbols=symbols), {"status": "OK"})[1])
    assert main.main(["stock-eod", "10/07/2026"]) == 0
    assert captured["date"] == "10/07/2026"



def test_stock_eod_help_has_no_indexes(capsys):
    with pytest.raises(SystemExit) as exc:
        main.build_parser().parse_args(["stock-eod", "--help"])
    assert exc.value.code == 0
    assert "--indexes" not in capsys.readouterr().out

def test_intraday_ingest_cli_calls_pipeline_with_symbols(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "run_intraday_ingest", lambda date, symbols=None: captured.update(date=date, symbols=symbols) or {"status": "OK"})
    assert main.main(["intraday-ingest", "10/07/2026", "--symbols", "ssi", "HPG"]) == 0
    assert captured == {"date": "10/07/2026", "symbols": ["SSI", "HPG"]}


def test_old_eod_command_is_not_registered():
    assert main.main(["eod"]) == 2


def test_intraday_does_not_call_daily_ingest(monkeypatch):
    monkeypatch.setattr(intraday, "run_intraday_features_with_summary", lambda **kwargs: {"status": "OK", "total_records": 3, "errors": []})
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


def test_backfill_cli_passes_exact_dates(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "run_backfill_pipeline", lambda start, end, symbols=None: captured.update(start=start, end=end, symbols=symbols) or {"status": "OK"})
    assert main.main(["backfill", "--from", "10/07/2026", "--to", "14/07/2026"]) == 0
    assert captured == {"start": "10/07/2026", "end": "14/07/2026", "symbols": None}


@pytest.mark.parametrize(
    ("command", "runner_name"),
    [("backfill-daily", "run_daily_backfill_pipeline"), ("backfill-intraday", "run_intraday_backfill_pipeline")],
)
def test_split_backfill_cli_passes_dates_and_normalized_symbols(monkeypatch, command, runner_name):
    captured = {}
    monkeypatch.setattr(main, runner_name, lambda start, end, symbols=None: captured.update(start=start, end=end, symbols=symbols) or {"status": "OK"})
    assert main.main([command, "--from", "10/07/2026", "--to", "14/07/2026", "--symbols", "ssi", " HPG ", "SSI"]) == 0
    assert captured == {"start": "10/07/2026", "end": "14/07/2026", "symbols": ["SSI", "HPG"]}


@pytest.mark.parametrize(
    ("command", "runner_name"),
    [("backfill-daily", "run_daily_backfill_pipeline"), ("backfill-intraday", "run_intraday_backfill_pipeline")],
)
def test_split_backfill_cli_aliases_and_status_exit_codes(monkeypatch, command, runner_name):
    captured = {}
    monkeypatch.setattr(main, runner_name, lambda start, end, symbols=None: captured.update(start=start, end=end) or {"status": "PARTIAL"})
    assert main.main([command, "--from-date", "10/07/2026", "--to-date", "10/07/2026"]) == 0
    assert captured == {"start": "10/07/2026", "end": "10/07/2026"}
    monkeypatch.setattr(main, runner_name, lambda *args, **kwargs: {"status": "FAILED"})
    assert main.main([command, "--from", "10/07/2026", "--to", "10/07/2026"]) == 1


def test_backfill_cli_aliases_work(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "run_backfill_pipeline", lambda start, end, symbols=None: captured.update(start=start, end=end, symbols=symbols) or {"status": "PARTIAL"})
    assert main.main(["backfill", "--from-date", "10/07/2026", "--to-date", "10/07/2026"]) == 0
    assert captured == {"start": "10/07/2026", "end": "10/07/2026", "symbols": None}


def test_backfill_cli_requires_both_dates(capsys):
    assert main.main(["backfill", "--from", "10/07/2026"]) == 2
    assert "required" in capsys.readouterr().err


def test_backfill_cli_failed_summary_returns_one(monkeypatch):
    monkeypatch.setattr(main, "run_backfill_pipeline", lambda start, end, symbols=None: {"status": "FAILED"})
    assert main.main(["backfill", "--from", "10/07/2026", "--to", "10/07/2026"]) == 1


def test_backfill_cli_invalid_range_returns_two(monkeypatch):
    monkeypatch.setattr(main, "run_backfill_pipeline", lambda start, end, symbols=None: (_ for _ in ()).throw(ValueError("from_date must be <= to_date")))
    assert main.main(["backfill", "--from", "11/07/2026", "--to", "10/07/2026"]) == 2


def test_refill_cli_requires_symbol_and_both_dates(capsys):
    commands = [
        ["refill", "--from", "01/07/2026", "--to", "02/07/2026"],
        ["refill", "--symbol", "SSI", "--to", "02/07/2026"],
        ["refill", "--symbol", "SSI", "--from", "01/07/2026"],
    ]
    assert [main.main(command) for command in commands] == [2, 2, 2]


def test_refill_cli_aliases_normalize_symbol_and_route(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "run_refill_pipeline", lambda start, end, symbol: captured.update(start=start, end=end, symbol=symbol) or {"status": "PARTIAL"})
    assert main.main(["refill", "--symbol", "ssi", "--from-date", "01/07/2026", "--to-date", "02/07/2026"]) == 0
    assert captured == {"start": "01/07/2026", "end": "02/07/2026", "symbol": "SSI"}


@pytest.mark.parametrize("symbol", ["", "   ", "ALL", "SSI HPG", "SSI,HPG"])
def test_refill_cli_rejects_invalid_symbol(monkeypatch, symbol):
    assert main.main(["refill", "--symbol", symbol, "--from", "01/07/2026", "--to", "02/07/2026"]) == 2


@pytest.mark.parametrize("start,end", [("02/07/2026", "01/07/2026"), ("01/01/2099", "02/01/2099")])
def test_refill_cli_rejects_invalid_range(monkeypatch, start, end):
    monkeypatch.setattr(main, "run_refill_pipeline", lambda *_a: (_ for _ in ()).throw(ValueError("invalid date range")))
    assert main.main(["refill", "--symbol", "SSI", "--from", start, "--to", end]) == 2


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


def test_daily_cli_normalizes_and_deduplicates_symbols(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "daily_run", lambda date, symbols=None: captured.update(date=date, symbols=symbols) or {"status": "OK"})
    assert main.main(["daily", "10/07/2026", "--symbols", "ssi", " HPG ", "SSI"]) == 0
    assert captured["symbols"] == ["SSI", "HPG"]


def test_stock_eod_cli_passes_symbols(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "run_stock_eod_pipeline", lambda date, symbols=None: captured.update(date=date, symbols=symbols) or {"status": "OK"})
    assert main.main(["stock-eod", "10/07/2026", "--symbols", "ssi", "HPG"]) == 0
    assert captured["symbols"] == ["SSI", "HPG"]


def test_backfill_cli_passes_symbols(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "run_backfill_pipeline", lambda start, end, symbols=None: captured.update(symbols=symbols) or {"status": "OK"})
    assert main.main(["backfill", "--from", "10/07/2026", "--to", "14/07/2026", "--symbols", "ssi", "SSI", "hpg"]) == 0
    assert captured["symbols"] == ["SSI", "HPG"]


def test_ingest_commands_reject_symbols_flag_without_values():
    commands = [
        ["daily", "10/07/2026", "--symbols"],
        ["intraday-ingest", "10/07/2026", "--symbols"],
        ["stock-eod", "10/07/2026", "--symbols"],
        ["backfill", "--from", "10/07/2026", "--to", "14/07/2026", "--symbols"],
        ["backfill-daily", "--from", "10/07/2026", "--to", "14/07/2026", "--symbols"],
        ["backfill-intraday", "--from", "10/07/2026", "--to", "14/07/2026", "--symbols"],
    ]
    assert [main.main(command) for command in commands] == [2, 2, 2, 2, 2, 2]


def test_features_daily_routes_source_specific_runner(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, 'run_daily_features_with_summary', lambda **kwargs: captured.update(kwargs) or {'status': 'OK'})
    assert main.main(['features-daily', '--mode', 'incremental', '--date', '10/07/2026', '--symbols', 'ssi']) == 0
    assert captured == {'symbols': ['SSI'], 'mode': 'incremental', 'target_date': '10/07/2026'}


def test_features_intraday_routes_and_rejects_daily(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, 'run_intraday_features_with_summary', lambda **kwargs: captured.update(kwargs) or {'status': 'OK'})
    assert main.main(['features-intraday', '--date', '10/07/2026', '--symbols', 'ssi', '--timeframes', '15m', '--as-of', '14:30']) == 0
    assert captured['timeframes'] == ('15m',) and captured['as_of'] == '14:30'
    assert main.main(['features-intraday', '--timeframes', '1d']) == 2
