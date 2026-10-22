import pytest
from src.ingest.workflows.stock_intraday import run_stock_intraday_pipeline

@pytest.mark.parametrize("date,symbols", [(None, ["SSI"]), ("19/10/2026", None)])
def test_manual_workflow_requires_explicit_scope(date, symbols):
    with pytest.raises(ValueError):
        run_stock_intraday_pipeline(date, symbols=symbols)


def test_workflow_only_delegates_to_manual_boundary(monkeypatch):
    seen = []
    def manual(date, **kwargs):
        seen.append((date, kwargs))
        return {"status": "OK"}
    monkeypatch.setattr("src.ingest.stock_intraday.manual.run_manual_intraday", manual)
    assert run_stock_intraday_pipeline("2026-10-20", symbols=["SSI"]) == {"status": "OK"}
    assert seen == [("2026-10-20", {"symbols": ["SSI"], "data_source": None, "write": False})]
