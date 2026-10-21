import pytest
from src.providers.ssi.capabilities import CapabilityUnavailableError

class Untouchable:
    def __getattr__(self, name):
        raise AssertionError(f"unexpected service access: {name}")

from src.ingest.stock_intraday.intraday_ingest import run_intraday_ingest
from src.ingest.stock_intraday.intraday_service import fetch_intraday_for_symbol_with_clients

@pytest.mark.parametrize("symbols", [None, [], ["ssi", "HPG"]])
def test_intraday_disabled_for_every_scope(symbols):
    with pytest.raises(CapabilityUnavailableError, match="stock_intraday"):
        run_intraday_ingest("19/10/2026", symbols=symbols)


def test_injected_clients_are_never_touched():
    with pytest.raises(CapabilityUnavailableError):
        fetch_intraday_for_symbol_with_clients(Untouchable(), Untouchable(), "SSI", "19/10/2026")
