import pytest
from src.providers.ssi.capabilities import CapabilityUnavailableError

class Untouchable:
    def __getattr__(self, name):
        raise AssertionError(f"unexpected service access: {name}")

from src.ingest.streaming.streaming_snapshot import run_streaming_ingest
from src.ingest.streaming.orderbook_snapshot import snapshot_orderbook, snapshot_orderbook_from_stream

@pytest.mark.parametrize("write", [False, True])
def test_capture_disabled_even_with_explicit_clients_and_write(write):
    with pytest.raises(CapabilityUnavailableError):
        run_streaming_ingest(["SSI"], [], ["quote"], write=write, client=Untouchable(), db=Untouchable())


def test_orderbook_never_contacts_services():
    with pytest.raises(CapabilityUnavailableError):
        snapshot_orderbook(["SSI"], Untouchable(), Untouchable())
    with pytest.raises(CapabilityUnavailableError):
        snapshot_orderbook_from_stream(["SSI"])
