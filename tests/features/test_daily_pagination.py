from datetime import date

import pandas as pd
import pytest

from src.features.runtime import fetch_stock_daily_rows
from tests.features.test_feature_engine import _DB, _Query, _mk_daily


def _rows(count=2505):
    dates = pd.bdate_range("2016-01-01", periods=count)
    return [_mk_daily(day.date().isoformat(), index + 1) for index, day in enumerate(dates)]


def test_daily_pagination_fetches_2505_unique_rows_and_short_last_page():
    rows = _rows()
    db = _DB([], daily_rows=rows)
    result = fetch_stock_daily_rows(db, "SSI", page_size=1000)
    assert len(result) == 2505
    assert len({row["trading_date"] for row in result}) == 2505
    assert result[0]["trading_date"] < result[-1]["trading_date"]
    assert db.table_calls.count("stock_daily") == 4  # includes terminal empty page


@pytest.mark.parametrize("limit", [400, 1000, 1400])
def test_newest_limit_is_exact_and_returned_oldest_first(limit):
    rows = _rows()
    db = _DB([], daily_rows=rows)
    result = fetch_stock_daily_rows(
        db, "SSI", order_desc=True, limit_total=limit, page_size=1000
    )
    expected = rows[-limit:]
    assert [row["trading_date"] for row in result] == [row["trading_date"] for row in expected]
    assert db.table_calls.count("stock_daily") == (limit + 999) // 1000


def test_daily_filters_are_rebuilt_for_every_page():
    rows = _rows()
    start = rows[300]["trading_date"]
    end = rows[2300]["trading_date"]
    db = _DB([], daily_rows=rows)
    result = fetch_stock_daily_rows(db, "SSI", start, end, page_size=700)
    assert result[0]["trading_date"] == start
    assert result[-1]["trading_date"] == end
    assert len(result) == 2001
    assert db.table_calls.count("stock_daily") == 4


def test_daily_page_size_must_be_positive():
    with pytest.raises(ValueError, match="page_size"):
        fetch_stock_daily_rows(_DB([]), "SSI", page_size=0)


def test_daily_pagination_survives_server_cap_below_requested_size():
    class CappedQuery(_Query):
        def range(self, start, end):
            return super().range(start, min(end, start + 499))

    class CappedDB(_DB):
        def table(self, name):
            self.table_calls.append(name)
            return CappedQuery(self.daily_rows)

    rows = _rows(2505)
    db = CappedDB([], daily_rows=rows)
    result = fetch_stock_daily_rows(db, "SSI", page_size=1000)
    assert [row["trading_date"] for row in result] == [row["trading_date"] for row in rows]
    assert db.table_calls.count("stock_daily") == 7  # six data pages + empty page
