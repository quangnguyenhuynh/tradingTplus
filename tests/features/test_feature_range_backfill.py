import main
import pytest

from src.features.backfill import normalize_feature_range
from src.features.runtime import atomic_replace_features, validate_replace_scope


def test_normalize_feature_range_is_inclusive_and_accepts_cli_dates():
    start, end = normalize_feature_range("01/07/2026", "29/07/2026")
    assert start.isoformat() == "2026-07-01"
    assert end.isoformat() == "2026-07-29"


def test_normalize_feature_range_rejects_reversed_range():
    with pytest.raises(ValueError, match="from_date must be <= to_date"):
        normalize_feature_range("29/07/2026", "01/07/2026")


def test_features_daily_routes_range_dates_and_symbols(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        main,
        "run_daily_feature_backfill",
        lambda start, end, symbols=None: captured.update(
            start=start, end=end, symbols=symbols
        )
        or {"status": "OK"},
    )

    assert main.main(
        [
            "features-daily",
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


def test_features_intraday_routes_range_timeframes(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        main,
        "run_intraday_feature_backfill",
        lambda start, end, symbols=None, timeframes=None: captured.update(
            start=start,
            end=end,
            symbols=symbols,
            timeframes=timeframes,
        )
        or {"status": "OK"},
    )

    assert main.main(
        [
            "features-intraday",
            "--from-date",
            "01/07/2026",
            "--to-date",
            "29/07/2026",
            "--symbols",
            "SSI",
            "--timeframes",
            "15m",
            "60m",
        ]
    ) == 0
    assert captured["timeframes"] == ("15m", "60m")


@pytest.mark.parametrize(
    "arguments",
    [
        ["features-daily", "--from", "01/07/2026"],
        ["features-daily", "--to", "01/07/2026"],
        ["features-daily", "--date", "01/07/2026", "--from", "01/07/2026", "--to", "02/07/2026"],
        ["features-daily", "--mode", "full", "--date", "01/07/2026"],
        ["features-daily", "--mode", "full", "--from", "01/07/2026", "--to", "02/07/2026"],
        ["features-intraday", "--from", "01/07/2026", "--to", "02/07/2026", "--as-of", "14:30"],
        ["features-daily"],
    ],
)
def test_feature_cli_rejects_invalid_execution_scope(arguments):
    assert main.main(arguments) == 2


def test_feature_cli_rejects_reversed_and_future_ranges():
    assert main.main(
        ["features-daily", "--from", "29/07/2026", "--to", "01/07/2026"]
    ) == 2
    assert main.main(
        ["features-daily", "--from", "01/08/2099", "--to", "02/08/2099"]
    ) == 2


def test_feature_range_rejects_non_persisted_intraday_timeframe():
    assert main.main(
        [
            "features-intraday",
            "--from",
            "01/07/2026",
            "--to",
            "02/07/2026",
            "--timeframes",
            "5m",
        ]
    ) == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        {"symbols": [], "timeframes": ["1d"], "start": "01/07/2026", "end": "02/07/2026"},
        {"symbols": ["SSI"], "timeframes": [], "start": "01/07/2026", "end": "02/07/2026"},
        {"symbols": ["SSI", "HPG"], "timeframes": ["1d"], "start": "01/07/2026", "end": "02/07/2026"},
        {"symbols": ["SSI"], "timeframes": ["1d"], "start": None, "end": "02/07/2026"},
    ],
)
def test_replace_scope_requires_exact_symbol_timeframe_and_range(kwargs):
    with pytest.raises(ValueError, match="requires exactly one symbol"):
        validate_replace_scope(**kwargs)


@pytest.mark.parametrize("timeframe", ["1m", "5m", "tick"])
def test_replace_scope_rejects_non_persisted_timeframe(timeframe):
    with pytest.raises(ValueError, match="persisted feature timeframes"):
        validate_replace_scope(
            symbols=["SSI"], timeframes=[timeframe],
            start="01/07/2026", end="02/07/2026",
        )


def test_replace_scope_rejects_blank_symbol_or_timeframe():
    for symbols, timeframes in [([""], ["1d"]), (["SSI"], [""])]:
        with pytest.raises(ValueError, match="requires exactly one symbol"):
            validate_replace_scope(
                symbols=symbols, timeframes=timeframes,
                start="01/07/2026", end="02/07/2026",
            )


def test_replace_scope_normalizes_scope_and_rejects_reversed_timestamps():
    assert validate_replace_scope(
        symbols=[" ssi "], timeframes=["15m"],
        start="2026-07-01T09:00:00+07:00",
        end="2026-07-01T10:00:00+07:00",
    ) == ("SSI", "15m")
    with pytest.raises(ValueError, match="start must be <= end"):
        validate_replace_scope(
            symbols=["SSI"], timeframes=["60m"],
            start="02/07/2026", end="01/07/2026",
        )


def test_atomic_replace_computes_before_one_rpc(monkeypatch):
    from src.features import runtime

    class DB:
        calls = []
        def health_check(self): return True
        def atomic_replace_features(self, **kwargs):
            self.calls.append(kwargs)
            return {"deleted_rows": 1, "replaced_rows": len(kwargs["replacement_rows"])}

    db = DB()
    monkeypatch.setattr(runtime, "SupabaseClient", lambda: db)
    monkeypatch.setattr(runtime, "fetch_stock_daily_rows", lambda *_a, **_k: [{
        "trading_date": "2026-07-01", "open_price": 10, "highest_price": 11,
        "lowest_price": 9, "close_price": 10.5, "total_traded_vol": 100,
        "total_traded_value": 1050,
    }])
    result = atomic_replace_features(
        symbols=["SSI"], timeframes=["1d"],
        start="01/07/2026", end="02/07/2026",
    )
    assert result["status"] == "OK"
    assert len(db.calls) == 1
    assert db.calls[0]["start_utc"].startswith("2026-06-30T17:00:00")
    assert db.calls[0]["end_exclusive_utc"].startswith("2026-07-02T17:00:00")


def test_replace_cli_rejects_missing_scope_and_routes_complete_scope(monkeypatch):
    assert main.main(["features-daily", "--mode", "replace"]) == 2
    monkeypatch.setattr(main, "atomic_replace_features", lambda **_kwargs: {"status": "OK"})
    assert main.main([
        "features-daily", "--mode", "replace", "--from", "01/07/2026",
        "--to", "02/07/2026", "--symbols", "SSI",
    ]) == 0
