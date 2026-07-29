import importlib.util
from pathlib import Path

import pytest

from src.features.backfill import normalize_feature_range


def _load_cli():
    path = Path("scripts/feature_backfill/run.py")
    spec = importlib.util.spec_from_file_location("feature_backfill_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalize_feature_range_is_inclusive_and_accepts_cli_dates():
    start, end = normalize_feature_range("01/07/2026", "29/07/2026")
    assert start.isoformat() == "2026-07-01"
    assert end.isoformat() == "2026-07-29"


def test_normalize_feature_range_rejects_reversed_range():
    with pytest.raises(ValueError, match="from_date must be <= to_date"):
        normalize_feature_range("29/07/2026", "01/07/2026")


def test_feature_backfill_cli_routes_daily_dates_and_symbols(monkeypatch):
    cli = _load_cli()
    captured = {}
    monkeypatch.setattr(
        cli,
        "run_daily_feature_backfill",
        lambda start, end, symbols=None: captured.update(
            start=start,
            end=end,
            symbols=symbols,
        )
        or {"status": "OK"},
    )

    assert cli.main(
        [
            "daily",
            "--from",
            "01/07/2026",
            "--to",
            "29/07/2026",
            "--symbols",
            "ssi",
            "HPG",
            "SSI",
        ]
    ) == 0
    assert captured == {
        "start": "01/07/2026",
        "end": "29/07/2026",
        "symbols": ["SSI", "HPG"],
    }


def test_feature_backfill_cli_routes_intraday_timeframes(monkeypatch):
    cli = _load_cli()
    captured = {}
    monkeypatch.setattr(
        cli,
        "run_intraday_feature_backfill",
        lambda start, end, symbols=None, timeframes=None: captured.update(
            start=start,
            end=end,
            symbols=symbols,
            timeframes=timeframes,
        )
        or {"status": "OK"},
    )

    assert cli.main(
        [
            "intraday",
            "--from",
            "01/07/2026",
            "--to",
            "29/07/2026",
            "--symbols",
            "SSI",
            "--timeframes",
            "15m",
            "60m",
        ]
    ) == 0
    assert captured["timeframes"] == ("15m", "60m")
