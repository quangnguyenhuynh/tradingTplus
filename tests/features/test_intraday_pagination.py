"""Regression coverage for every intraday PostgREST feature reader."""

import pandas as pd
import pytest

from src.features.runtime import (
    fetch_intraday_trading_session_window,
    fetch_stock_intraday_paginated,
)


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db):
        self.db = db
        self.filters = []
        self.orders = []
        self.bounds = (0, 999)

    def select(self, *_args): return self
    def eq(self, key, value): self.filters.append(("eq", key, value)); return self
    def gte(self, key, value): self.filters.append(("gte", key, value)); return self
    def lt(self, key, value): self.filters.append(("lt", key, value)); return self
    def order(self, key, desc=False): self.orders.append((key, desc)); return self
    def range(self, start, end): self.bounds = (start, min(end, start + self.db.cap - 1)); return self

    def execute(self):
        self.db.calls.append((tuple(self.filters), tuple(self.orders), self.bounds))
        rows = list(self.db.rows)
        for operation, key, value in self.filters:
            if operation == "eq": rows = [row for row in rows if row[key] == value]
            elif operation == "gte": rows = [row for row in rows if row[key] >= value]
            else: rows = [row for row in rows if row[key] < value]
        for key, desc in reversed(self.orders):
            rows.sort(key=lambda row: row[key], reverse=desc)
        start, end = self.bounds
        page = rows[start:end + 1]
        return _Result(self.db.repeat if self.db.repeat is not None and start else page)


class _DB:
    def __init__(self, rows, cap=500, repeat=None):
        self.rows, self.cap, self.repeat = rows, cap, repeat
        self.calls = []
    def get(self): return self
    def table(self, name): assert name == "stock_intraday"; return _Query(self)
    def _with_retry(self, action, **_kwargs): return action()


def _rows(count=2505):
    base = pd.Timestamp("2026-01-02T02:00:00Z")
    return [{
        "symbol": "SSI", "timeframe": "1m",
        "time": (base + pd.Timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "open": i + 1, "high": i + 2, "low": i, "close": i + 1.5,
        "volume": i + 10, "value": i + 100,
    } for i in range(count)]


def test_intraday_paginated_cap_filters_boundaries_terminal_and_limit():
    rows = _rows()
    start, end = rows[100]["time"], rows[2400]["time"]
    db = _DB(rows)
    loaded = fetch_stock_intraday_paginated(
        db, "SSI", gte_time=start, lt_time=end, page_size=1000,
    )
    assert loaded == rows[100:2400]
    assert len({row["time"] for row in loaded}) == 2300
    assert len(db.calls) == 6  # five capped data pages and terminal empty page
    expected_filters = {
        ("eq", "symbol", "SSI"), ("eq", "timeframe", "1m"),
        ("gte", "time", start), ("lt", "time", end),
    }
    assert all(set(filters) == expected_filters for filters, _, _ in db.calls)
    assert [bounds[0] for _, _, bounds in db.calls] == [0, 500, 1000, 1500, 2000, 2300]

    limited_db = _DB(rows)
    limited = fetch_stock_intraday_paginated(
        limited_db, "SSI", order_desc=True, page_size=1000, limit_total=1250,
    )
    assert len(limited) == 1250
    assert limited == list(reversed(rows))[:1250]
    assert [bounds[0] for _, _, bounds in limited_db.calls] == [0, 500, 1000]


@pytest.mark.parametrize("page_size", [0, -1])
def test_intraday_paginated_rejects_invalid_page_size(page_size):
    with pytest.raises(ValueError, match="page_size"):
        fetch_stock_intraday_paginated(_DB([]), "SSI", page_size=page_size)


def test_intraday_paginated_repeated_page_fails_safely():
    rows = _rows(20)
    with pytest.raises(RuntimeError, match="Repeated PostgREST page"):
        fetch_stock_intraday_paginated(
            _DB(rows, cap=10, repeat=rows[:10]), "SSI", page_size=10,
        )


def test_250th_session_boundary_split_across_capped_pages_is_complete():
    dates = pd.bdate_range("2025-01-02", periods=251)
    rows = []
    for day_index, day in enumerate(dates):
        start = pd.Timestamp(day.date(), tz="Asia/Ho_Chi_Minh").replace(hour=9)
        for minute in range(7):
            rows.append({
                **_rows(1)[0],
                "time": (start + pd.Timedelta(minutes=minute)).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                "close": 100 + day_index + minute / 10,
            })
    # Descending page cap 1,747 puts four candles of the oldest selected day
    # on page one and its remaining three on page two.
    db = _DB(rows, cap=1747)
    loaded = fetch_intraday_trading_session_window(
        db, "SSI", "2027-01-01T00:00:00Z", trading_sessions=250, page_size=2000,
    )
    observed = pd.to_datetime([row["time"] for row in loaded], utc=True).tz_convert("Asia/Ho_Chi_Minh").date
    assert len(set(observed)) == 250
    assert sum(value == dates[1].date() for value in observed) == 7
    assert dates[0].date() not in observed
    assert [bounds[0] for _, _, bounds in db.calls] == [0, 1747]
    assert all(("eq", "symbol", "SSI") in filters for filters, _, _ in db.calls)
    assert all(("eq", "timeframe", "1m") in filters for filters, _, _ in db.calls)
