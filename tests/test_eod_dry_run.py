import importlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

dry = importlib.import_module("src.pipeline.eod_dry_run")


class _SSI:
    def __init__(self, daily=None, candles=None):
        self.daily = daily
        self.candles = candles or []

    def get_daily_price(self, symbol, date):
        return self.daily

    def get_intraday(self, symbol, date):
        return self.candles


def _daily():
    return {
        "RefPrice": "10.1",
        "CeilingPrice": "11.1",
        "FloorPrice": "9.1",
        "ClosePrice": "10.5",
        "TotalMatchVol": "1000",
    }


def _candle(i: int):
    ts = pd.Timestamp("2024-07-05 09:15:00") + pd.Timedelta(minutes=i)
    close = 10.5 + i / 10
    return {
        "Time": ts.strftime("%H:%M:%S"),
        "Open": str(close - 0.1),
        "High": str(close + 0.2),
        "Low": str(close - 0.2),
        "Close": str(close),
        "Volume": str(100 + i),
        "Value": "999999",
    }


def test_eod_dry_run_does_not_call_any_db_upsert(monkeypatch, capsys):
    class ExplodingSupabase:
        def __init__(self):
            raise AssertionError("dry-run must not instantiate SupabaseClient")

    monkeypatch.setattr(dry, "SSIApi", lambda: _SSI(daily=_daily(), candles=[_candle(i) for i in range(5)]))
    monkeypatch.setattr("src.database.client.SupabaseClient", ExplodingSupabase)

    summary = dry.run_eod_dry_run("05/07/2024", ["SSI"], ["1m"], json_output=False)

    assert summary["read_only"] is True
    assert summary["symbols"][0]["stock_intraday_record_count"] == 5
    assert "Safety: read-only" in capsys.readouterr().out


def test_eod_dry_run_feature_output_contains_all_requested_timeframes(monkeypatch):
    monkeypatch.setattr(dry, "SSIApi", lambda: _SSI(daily=_daily(), candles=[_candle(i) for i in range(30)]))

    summary = dry.run_eod_dry_run("05/07/2024", ["SSI"], ["1m", "5m", "15m"], json_output=True)
    symbol_summary = summary["symbols"][0]

    assert symbol_summary["feature_timeframes_calculated"] == ["1m", "5m", "15m"]
    assert set(symbol_summary["feature_row_count_by_timeframe"]) == {"1m", "5m", "15m"}
    assert symbol_summary["feature_row_count_by_timeframe"]["1m"] == 30
    assert symbol_summary["feature_preview_by_timeframe"]["1m"][-1]["close"] is not None


def test_eod_dry_run_missing_daily_skips_symbol_safely(monkeypatch):
    monkeypatch.setattr(dry, "SSIApi", lambda: _SSI(daily=None, candles=[_candle(0)]))

    summary = dry.run_eod_dry_run("05/07/2024", ["SSI"], ["1m"], json_output=True)
    symbol_summary = summary["symbols"][0]

    assert symbol_summary["daily_found"] is False
    assert symbol_summary["feature_timeframes_calculated"] == []
    assert "missing daily price" in symbol_summary["warnings"][0]


def test_eod_dry_run_missing_intraday_skips_symbol_safely(monkeypatch):
    monkeypatch.setattr(dry, "SSIApi", lambda: _SSI(daily=_daily(), candles=[]))

    summary = dry.run_eod_dry_run("05/07/2024", ["SSI"], ["1m"], json_output=True)
    symbol_summary = summary["symbols"][0]

    assert symbol_summary["daily_found"] is True
    assert symbol_summary["intraday_candle_count"] == 0
    assert symbol_summary["feature_timeframes_calculated"] == []
    assert "missing intraday candles" in symbol_summary["warnings"][0]
