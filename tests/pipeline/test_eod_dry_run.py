import pytest
from src.providers.ssi.capabilities import CapabilityUnavailableError

class Untouchable:
    def __getattr__(self, name):
        raise AssertionError(f"unexpected service access: {name}")

from src.diagnostics.eod_dry_run import run_eod_dry_run


def test_combined_dry_run_reports_unavailable_before_fetching():
    with pytest.raises(CapabilityUnavailableError):
        run_eod_dry_run(date="19/10/2026", symbols=["SSI"], timeframes=["1d"])
