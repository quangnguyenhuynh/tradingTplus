import pytest
from src.providers.ssi.capabilities import CapabilityUnavailableError

class Untouchable:
    def __getattr__(self, name):
        raise AssertionError(f"unexpected service access: {name}")

from src.ingest.maintenance.refill import run_refill_pipeline

@pytest.mark.parametrize("symbol", ["SSI", "", "ALL"])
def test_refill_fails_before_any_daily_or_feature_work(symbol):
    with pytest.raises(CapabilityUnavailableError):
        run_refill_pipeline("01/07/2026", "02/07/2026", symbol)
