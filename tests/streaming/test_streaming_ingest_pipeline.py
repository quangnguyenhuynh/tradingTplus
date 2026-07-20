from src.pipeline.streaming_snapshot import run_streaming_ingest


class FakeClient:
    def __init__(self, messages=None):
        self.messages = list(messages or [])
        self.subscribed_channels = []
        self.closed = False
    def connect(self): pass
    def subscribe_many(self, channels): self.subscribed_channels.extend(channels)
    def listen(self, timeout_sec, max_messages=None):
        out, self.messages = self.messages[:], []
        return out
    def parse_message(self, raw):
        return {"data_type": raw.get("DataType"), "content": raw.get("Content"), "raw": raw}
    def close(self): self.closed = True


class FakeDB:
    def __init__(self): self.calls = []
    def __getattr__(self, name):
        if name.startswith("upsert_stream_"):
            def call(records): self.calls.append((name, list(records)))
            return call
        raise AttributeError(name)


def test_dry_run_does_not_write_db():
    client = FakeClient([{"DataType":"X-QUOTE","Content":{"RType":"QUOTE","Symbol":"SSI","TradingDate":"2026-07-17","Time":"10:00:00"}}])
    db = FakeDB()
    summary = run_streaming_ingest(["SSI"], [], ["quote"], timeout_sec=1, write=False, client=client, db=db)
    assert summary["status"] == "OK"
    assert db.calls == []
    assert client.closed


def test_invalid_clean_writes_raw_only_in_write_mode():
    client = FakeClient([{"DataType":"B","Content":{"RType":"B","Symbol":"SSI","TradingDate":"2026-07-17","Time":"10:00:00","Open":10,"High":9,"Low":8,"Close":10}}])
    db = FakeDB()
    summary = run_streaming_ingest(["SSI"], [], ["realtime-bar"], timeout_sec=1, write=True, client=client, db=db)
    assert summary["status"] == "PARTIAL"
    raw_call = next(c for c in db.calls if c[0] == "upsert_stream_raw")
    assert raw_call[1][0]["validation_status"] == "ERROR"
    bar_call = next(c for c in db.calls if c[0] == "upsert_stream_bar_snapshot")
    assert bar_call[1] == []


def test_empty_timeout_returns_empty():
    client = FakeClient([])
    summary = run_streaming_ingest(["SSI"], [], ["quote"], timeout_sec=1, write=False, client=client)
    assert summary["status"] == "EMPTY"
