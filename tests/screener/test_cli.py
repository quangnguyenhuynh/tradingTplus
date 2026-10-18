import main


def test_screener_read_only_by_default(monkeypatch):
    captured = {}
    def fake_runner(date, symbols=None, apply=False):
        captured.update(date=date, symbols=symbols, apply=apply)
        return {"status": "OK"}
    monkeypatch.setattr(main, "run_stock_screener", fake_runner)
    assert main.main(["stock-screener", "--date", "14/08/2026", "--symbols", "ssi"]) == 0
    assert captured == {"date": "14/08/2026", "symbols": ["SSI"], "apply": False}


def test_screener_explicit_apply(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        main, "run_stock_screener",
        lambda date, symbols=None, apply=False: captured.update(apply=apply) or {"status": "PARTIAL"},
    )
    assert main.main(["stock-screener", "--date", "14/08/2026", "--apply"]) == 0
    assert captured["apply"] is True
