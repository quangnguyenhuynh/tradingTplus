from src.pipeline import ingest_check


class _Result:
    def __init__(self, data=None, count=0):
        self.data = data or []
        self.count = count


class _Query:
    def __init__(self, db, table):
        self.db = db
        self.table = table
        self.filters = []
        self.select_args = None

    def select(self, *args, **kwargs):
        self.select_args = (args, kwargs)
        return self

    def eq(self, key, value):
        self.filters.append(("eq", key, value))
        return self

    def gte(self, key, value):
        self.filters.append(("gte", key, value))
        return self

    def lt(self, key, value):
        self.filters.append(("lt", key, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        self.db.executed.append((self.table, tuple(self.filters), self.select_args))
        if self.table == "stock_daily":
            return _Result(data=[{"symbol": "SSI"}], count=1)
        if self.table == "stock_intraday":
            return _Result(data=[], count=0)
        if self.table == "orderbook_snapshot":
            return _Result(count=2)
        return _Result(count=0)


class _Client:
    def __init__(self, db):
        self.db = db

    def table(self, table):
        return _Query(self.db, table)


class _DB:
    def __init__(self):
        self.client = _Client(self)
        self.executed = []

    def _with_retry(self, action, action_name, **_kwargs):
        return action()

    def get_symbols(self):
        return ["SSI"]


def test_check_ingest_counts_orderbook_snapshots_in_vietnam_date_range(monkeypatch):
    db = _DB()
    monkeypatch.setattr(ingest_check, "SupabaseClient", lambda: db)

    summary = ingest_check.check_ingest("10/07/2026")

    assert summary["orderbook_snapshot_count"] == 2
    assert summary["utc_range"] == {
        "start": "2026-07-09T17:00:00Z",
        "end": "2026-07-10T17:00:00Z",
    }
    orderbook_queries = [entry for entry in db.executed if entry[0] == "orderbook_snapshot"]
    assert orderbook_queries == [
        (
            "orderbook_snapshot",
            (
                ("gte", "time", "2026-07-09T17:00:00Z"),
                ("lt", "time", "2026-07-10T17:00:00Z"),
            ),
            (("*",), {"count": "exact"}),
        )
    ]
