import pytest
from src.providers.ssi.capabilities import CapabilityUnavailableError

class Untouchable:
    def __getattr__(self, name):
        raise AssertionError(f"unexpected service access: {name}")

from src.ingest.workflows.stock_intraday import run_stock_intraday_pipeline

@pytest.mark.parametrize("date", [None, "19/10/2026"])
def test_disabled_workflow_does_not_resolve_scope(date):
    with pytest.raises(CapabilityUnavailableError):
        run_stock_intraday_pipeline(date, symbols=["SSI"])
