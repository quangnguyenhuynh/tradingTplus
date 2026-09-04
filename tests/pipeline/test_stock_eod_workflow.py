from pathlib import Path


def test_stock_eod_workflow_uses_renamed_stock_only_command():
    text = Path(".github/workflows/stock-eod.yml").read_text()
    assert "name: TradingTPlus Stock EOD Pipeline" in text
    assert "  stock-eod:" in text
    assert "tradingtplus-stock-eod-" in text
    assert "python main.py stock-eod" in text
    assert "python main.py eod" not in text
    assert not Path(".github/workflows/eod.yml").exists()


def test_index_eod_remains_independent():
    text = Path(".github/workflows/index-eod.yml").read_text()
    assert "python main.py index-daily" in text
    for forbidden_command in (
        "python main.py stock-eod",
        "python main.py stock-intraday",
        "python main.py features",
        "python main.py signals",
        "python main.py backtest",
    ):
        assert forbidden_command not in text
