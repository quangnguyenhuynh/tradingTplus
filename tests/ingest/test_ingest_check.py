from datetime import datetime, timedelta, timezone

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
        self.range_args = None

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

    def in_(self, key, value):
        self.filters.append(("in", key, tuple(value)))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, *args, **_kwargs):
        self.range_args = args
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        self.db.executed.append((self.table, tuple(self.filters), self.select_args))
        symbol_filter = next((set(values) for kind, key, values in self.filters if kind == "in" and key == "symbol"), None)
        if self.table == "stock_daily":
            rows = self.db.daily_rows
            if symbol_filter is not None:
                rows = [row for row in rows if row["symbol"] in symbol_filter]
            if self.range_args:
                rows = rows[self.range_args[0]:self.range_args[1] + 1]
            return _Result(data=rows, count=len(rows))
        if self.table == "stock_intraday":
            rows = self.db.intraday_rows
            if symbol_filter is not None:
                rows = [row for row in rows if row["symbol"] in symbol_filter]
            if self.range_args:
                rows = rows[self.range_args[0]:self.range_args[1] + 1]
            return _Result(data=rows, count=len(rows))
        if self.table == "orderbook_snapshot":
            return _Result(count=2)
        return _Result(count=0)


class _Client:
    def __init__(self, db):
        self.db = db

    def table(self, table):
        return _Query(self.db, table)


class _DB:
    def __init__(self, intraday_rows=None, daily_rows=None, symbols=None):
        self.client = _Client(self)
        self.executed = []
        self.intraday_rows = intraday_rows or []
        self.daily_rows = daily_rows if daily_rows is not None else [{"symbol": "SSI"}]
        self.symbols = symbols or ["SSI"]

    def _with_retry(self, action, action_name, **_kwargs):
        return action()

    def get_symbols(self):
        return self.symbols


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


def _ssi_style_day_times():
    """Build continuous 1m buckets plus SSI-style lunch/close boundaries."""
    ranges = (
        (datetime(2026, 7, 20, 2, 0, 17, tzinfo=timezone.utc), 150),
        (datetime(2026, 7, 20, 6, 0, 11, tzinfo=timezone.utc), 90),
    )
    times = [
        (start + timedelta(minutes=offset)).isoformat().replace("+00:00", "Z")
        for start, count in ranges
        for offset in range(count)
    ]
    return times + ["2026-07-20T04:30:09Z", "2026-07-20T07:30:08Z", "2026-07-20T07:45:00Z"]


def _intraday_rows(times):
    return [{"symbol": "SSI", "time": value, "timeframe": "1m"} for value in times]


def test_completeness_ok_for_2026_07_20_ssi_style_boundaries():
    times = _ssi_style_day_times()

    summary = ingest_check._symbol_intraday_summary("SSI", _intraday_rows(times), has_daily=True)

    assert summary["intraday_candle_count"] == 243
    assert summary["missing_interval_count"] == 0
    assert summary["missing_minutes"] == 0
    assert summary["status"] == "OK"


def test_short_empty_bucket_is_reported_without_failing_completeness():
    times = _ssi_style_day_times()
    times.remove("2026-07-20T06:27:11Z")

    summary = ingest_check._symbol_intraday_summary("SSI", _intraday_rows(times), has_daily=True)

    assert summary["missing_interval_count"] == 1
    assert summary["missing_minutes"] == 1
    assert summary["empty_minute_bucket_count"] == 1
    assert summary["gap_status"] == "OBSERVED"
    assert summary["status"] == "OK"


def test_five_isolated_pdr_style_empty_buckets_remain_ok():
    times = _ssi_style_day_times()
    for value in [
        "2026-07-20T02:10:17Z",
        "2026-07-20T02:30:17Z",
        "2026-07-20T03:10:17Z",
        "2026-07-20T03:30:17Z",
        "2026-07-20T04:10:17Z",
    ]:
        times.remove(value)

    summary = ingest_check._symbol_intraday_summary("PDR", _intraday_rows(times), has_daily=True)

    assert summary["missing_interval_count"] == 5
    assert summary["missing_minutes"] == 5
    assert summary["gap_status"] == "OBSERVED"
    assert summary["status"] == "OK"


def test_missing_entire_afternoon_session_is_structural_warning():
    times = [value for value in _ssi_style_day_times() if value < "2026-07-20T06:00:00Z"]

    summary = ingest_check._symbol_intraday_summary("SSI", _intraday_rows(times), has_daily=True)

    assert "missing_afternoon_session" in summary["structural_gap_reasons"]
    assert summary["gap_status"] == "STRUCTURAL"
    assert summary["status"] == "WARNING"


def test_long_continuous_gap_is_structural_warning():
    times = _ssi_style_day_times()
    times = [value for value in times if not ("2026-07-20T02:30:00Z" <= value < "2026-07-20T02:50:00Z")]

    summary = ingest_check._symbol_intraday_summary("SSI", _intraday_rows(times), has_daily=True)

    assert summary["longest_gap_minutes"] == 20
    assert "long_continuous_gap" in summary["structural_gap_reasons"]
    assert summary["status"] == "WARNING"


def test_short_gaps_do_not_make_check_ingest_or_eod_completeness_partial(monkeypatch):
    times = _ssi_style_day_times()
    for value in [
        "2026-07-20T02:10:17Z",
        "2026-07-20T02:30:17Z",
        "2026-07-20T03:10:17Z",
        "2026-07-20T03:30:17Z",
        "2026-07-20T04:10:17Z",
    ]:
        times.remove(value)
    db = _DB(_intraday_rows(times))
    monkeypatch.setattr(ingest_check, "SupabaseClient", lambda: db)

    summary = ingest_check.check_ingest("20/07/2026")

    assert summary["per_symbol"][0]["missing_minutes"] == 5
    assert summary["incomplete_intraday_count"] == 0
    assert summary["status"] == "OK"


def test_completeness_duplicate_detection_is_unchanged():
    times = _ssi_style_day_times()
    times.append(times[0])

    summary = ingest_check._symbol_intraday_summary("SSI", _intraday_rows(times), has_daily=True)

    assert summary["duplicate_count"] == 1
    assert summary["status"] == "WARNING"


def test_scoped_completeness_excludes_unrequested_symbols_and_never_queries_index(monkeypatch):
    times = _ssi_style_day_times()
    rows = _intraday_rows(times) + [
        {"symbol": "FPT", "time": value, "timeframe": "1m"} for value in times
    ]
    db = _DB(rows, daily_rows=[{"symbol": "SSI"}, {"symbol": "FPT"}], symbols=["SSI", "HPG", "FPT"])
    monkeypatch.setattr(ingest_check, "SupabaseClient", lambda: db)

    summary = ingest_check.check_ingest("20/07/2026", symbols=["ssi"])

    assert summary["symbol_scope"] == "EXPLICIT"
    assert summary["symbols"] == ["SSI"]
    assert summary["symbol_count"] == 1
    assert summary["stock_daily_count"] == 1
    assert summary["stock_intraday_count"] == len(times)
    assert summary["intraday_symbol_count"] == 1
    assert summary["missing_stock_daily_symbols"] == []
    assert summary["missing_intraday_symbols"] == []
    assert [row["symbol"] for row in summary["per_symbol"]] == ["SSI"]
    assert summary["index_daily_count"] == 0
    scoped_queries = [entry for entry in db.executed if entry[0] in {"stock_daily", "stock_intraday"}]
    assert all(("in", "symbol", ("SSI",)) in entry[1] for entry in scoped_queries)
    assert all(entry[0] != "index_daily" for entry in db.executed)
