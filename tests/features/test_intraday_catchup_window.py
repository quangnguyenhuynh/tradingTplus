"""Watermark-anchored intraday incremental catch-up regressions.

These cases verify the DI-01 contract for ``calculate_intraday_features_for_symbol``
and its shared read helper ``fetch_intraday_catchup_window``:

* warm-up is anchored at the earliest output start (watermark + 1ns), not the
  target boundary, so a catch-up older than 250 sessions still reads enough
  prior history instead of silently dropping the earliest output sessions;
* the full catch-up ``[output_start, target_end)`` is read, and every timeframe
  is computed before any upsert (a read/calculation failure leaves the symbol
  with zero writes);
* no watermark writes only the target day; watermark at/after the target is a
  zero-write no-op; distinct per-timeframe watermarks are honored independently;
* low server caps paginate, repeated pages fail explicitly, and repeated runs
  are idempotent.

All fixtures are synthetic and in-memory; no SSI, Supabase, or network access is
used.
"""

import socket

import pandas as pd
import pytest

import src.features.stock.intraday as intraday_flow
from src.features.stock.runtime import fetch_intraday_catchup_window


VN_TZ = "Asia/Ho_Chi_Minh"


def _daily_rows(session_count, start="2024-01-02"):
    return [
        {
            "trading_date": stamp.date().isoformat(),
            "open_price": 100.0 + i,
            "highest_price": 110.0 + i,
            "lowest_price": 90.0 + i,
            "close_price": 105.0 + i,
            "total_traded_vol": 1000 + i,
            "total_traded_value": 10000 + i,
        }
        for i, stamp in enumerate(pd.bdate_range(start, periods=session_count))
    ]


def _intraday_rows(session_count, start="2024-01-02", bars_per_session=4):
    rows = []
    for i, stamp in enumerate(pd.bdate_range(start, periods=session_count)):
        local = pd.Timestamp(stamp.date(), tz=VN_TZ)
        for minute in range(bars_per_session):
            ts = (local.replace(hour=9) + pd.Timedelta(minutes=minute)).tz_convert("UTC")
            rows.append(
                {
                    "symbol": "SSI",
                    "timeframe": "1m",
                    "time": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "open": 100.0 + i,
                    "high": 101.0 + i,
                    "low": 99.0 + i,
                    "close": 100.5 + i,
                    "volume": 100 + i,
                    "value": 10050 + i,
                }
            )
    return rows


def _feature_row(timeframe, watermark):
    return {
        "symbol": "SSI",
        "timeframe": timeframe,
        "time": watermark.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _bucket_watermark(session_date, timeframe="15m"):
    """A realistic persisted feature time: the first (only) bucket of a session."""
    return pd.Timestamp(session_date, tz=VN_TZ).replace(hour=9).tz_convert("UTC")


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db, table_name, rows):
        self.db = db
        self.table_name = table_name
        self.rows = rows
        self.filters = []
        self.orders = []
        self.bounds = (0, 999)

    def select(self, *_args):
        return self

    def eq(self, key, value):
        self.filters.append(("eq", key, value))
        return self

    def gte(self, key, value):
        self.filters.append(("gte", key, value))
        return self

    def lte(self, key, value):
        self.filters.append(("lte", key, value))
        return self

    def lt(self, key, value):
        self.filters.append(("lt", key, value))
        return self

    def order(self, key, desc=False):
        self.orders.append((key, desc))
        return self

    def range(self, start, end):
        self.bounds = (start, min(end, start + self.db.cap - 1))
        return self

    def execute(self):
        self.db.calls.append(
            (self.table_name, tuple(self.filters), tuple(self.orders), self.bounds)
        )
        rows = list(self.rows)
        for operation, key, value in self.filters:
            if operation == "eq":
                rows = [row for row in rows if row.get(key) == value]
            elif operation == "gte":
                rows = [row for row in rows if row.get(key) >= value]
            elif operation == "lte":
                rows = [row for row in rows if row.get(key) <= value]
            else:
                rows = [row for row in rows if row.get(key) < value]
        for key, desc in reversed(self.orders):
            rows.sort(key=lambda row: row[key], reverse=desc)
        start, end = self.bounds
        page = rows[start : end + 1]
        if self.db.repeat is not None and start:
            return _Result(self.db.repeat)
        return _Result(page)


class _DB:
    def __init__(self, intraday=None, daily=None, features=None, cap=1000, repeat=None):
        self.intraday = intraday or []
        self.daily = daily or []
        self.features = features or []
        self.cap = cap
        self.repeat = repeat
        self.calls = []
        self.upsert_calls = []

    def get(self):
        return self

    def table(self, name):
        if name == "stock_daily":
            rows = self.daily
        elif name == "stock_features":
            rows = self.features
        else:
            rows = self.intraday
        return _Query(self, name, rows)

    def _with_retry(self, action, action_name=None):
        return action()

    def _upsert_in_batches(self, table_name, records, on_conflict=None, batch_size=1000):
        self.upsert_calls.append((table_name, list(records), on_conflict, batch_size))


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    def _deny(*_args, **_kwargs):
        raise AssertionError("network access is not permitted in catch-up contract tests")

    monkeypatch.setattr(socket.socket, "connect", _deny)
    monkeypatch.setattr(socket, "create_connection", _deny)


def _session_dates(rows):
    return sorted(
        {
            pd.to_datetime(row["time"], utc=True).tz_convert(VN_TZ).date()
            for row in rows
        }
    )


def test_catchup_window_reads_warmup_before_output_start_and_full_catchup():
    sessions = 520
    rows = _intraday_rows(sessions)
    dates = _session_dates(rows)
    output_start = dates[260].isoformat() + "T00:00:00Z"
    end = (pd.Timestamp(dates[-1]) + pd.Timedelta(days=1)).isoformat() + "T00:00:00Z"

    loaded = fetch_intraday_catchup_window(
        _DB(intraday=rows), "SSI", output_start, end, trading_sessions=250
    )
    loaded_dates = _session_dates(loaded)
    assert loaded_dates[0] == dates[10]  # 250 sessions before output start
    assert loaded_dates[-1] == dates[-1]
    assert len(loaded_dates) == 250 + (sessions - 260)  # warm-up + catch-up
    # oldest-first and complete (no gap, no duplicate)
    assert loaded == sorted(loaded, key=lambda r: r["time"])
    assert len({row["time"] for row in loaded}) == len(loaded)


def test_catchup_window_anchors_warmup_at_output_start_not_target():
    sessions = 520
    rows = _intraday_rows(sessions)
    dates = _session_dates(rows)
    output_start = dates[260].isoformat() + "T00:00:00Z"
    end = (pd.Timestamp(dates[-1]) + pd.Timedelta(days=1)).isoformat() + "T00:00:00Z"

    loaded = fetch_intraday_catchup_window(
        _DB(intraday=rows), "SSI", output_start, end, trading_sessions=250
    )
    loaded_dates = _session_dates(loaded)
    assert loaded_dates[0] == dates[10]
    # The warm-up + catch-up spans more than 250 sessions because the catch-up
    # is not capped to the newest 250 sessions.
    assert len(loaded_dates) > 250


def test_incremental_old_watermark_covers_full_catchup(monkeypatch):
    sessions = 520
    rows = _intraday_rows(sessions)
    daily = _daily_rows(sessions)
    dates = _session_dates(rows)
    watermark = _bucket_watermark(dates[259])
    target_date = dates[-1]

    db = _DB(
        intraday=rows,
        daily=daily,
        features=[_feature_row("15m", watermark)],
    )
    monkeypatch.setattr(intraday_flow, "SupabaseClient", lambda: db)

    total = intraday_flow.calculate_intraday_features_for_symbol(
        "SSI", timeframes=["15m"], mode="incremental", target_date=target_date
    )
    assert total > 0
    assert len(db.upsert_calls) == 1
    records = db.upsert_calls[0][1]
    output_dates = sorted(
        {
            pd.to_datetime(record["time"], utc=True).tz_convert(VN_TZ).date()
            for record in records
        }
    )
    # The full catch-up span is covered: every session strictly after the
    # watermark through the target, not just the newest 250 sessions.
    assert output_dates[0] == dates[260]
    assert output_dates[-1] == target_date
    assert len(output_dates) == sessions - 260
    # First output row must have warm-up (ema50 non-NULL, not a cold start).
    first_record = sorted(records, key=lambda r: r["time"])[0]
    assert first_record["ema50"] is not None


def test_incremental_no_watermark_writes_only_target_day(monkeypatch):
    sessions = 60
    rows = _intraday_rows(sessions)
    daily = _daily_rows(sessions)
    dates = _session_dates(rows)
    target_date = dates[-1]

    db = _DB(intraday=rows, daily=daily, features=[])
    monkeypatch.setattr(intraday_flow, "SupabaseClient", lambda: db)

    total = intraday_flow.calculate_intraday_features_for_symbol(
        "SSI", timeframes=["15m"], mode="incremental", target_date=target_date
    )
    assert total > 0
    records = db.upsert_calls[0][1]
    output_dates = {
        pd.to_datetime(record["time"], utc=True).tz_convert(VN_TZ).date()
        for record in records
    }
    assert output_dates == {target_date}


def test_incremental_different_watermarks_per_timeframe(monkeypatch):
    sessions = 60
    rows = _intraday_rows(sessions)
    daily = _daily_rows(sessions)
    dates = _session_dates(rows)
    target_date = dates[-1]
    # 15m watermark is 2 days behind; 60m watermark is 1 day behind.
    wm_15 = _bucket_watermark(dates[-3])
    wm_60 = _bucket_watermark(dates[-2])

    db = _DB(
        intraday=rows,
        daily=daily,
        features=[_feature_row("15m", wm_15), _feature_row("60m", wm_60)],
    )
    monkeypatch.setattr(intraday_flow, "SupabaseClient", lambda: db)

    intraday_flow.calculate_intraday_features_for_symbol(
        "SSI", timeframes=["15m", "60m"], mode="incremental", target_date=target_date
    )
    assert len(db.upsert_calls) == 2
    by_timeframe = {}
    for _, records, _, _ in db.upsert_calls:
        tf = records[0]["timeframe"]
        by_timeframe[tf] = sorted(
            {
                pd.to_datetime(record["time"], utc=True).tz_convert(VN_TZ).date()
                for record in records
            }
        )
    # Each timeframe starts after its own watermark, not the other's.
    assert by_timeframe["15m"] == [dates[-2], dates[-1]]
    assert by_timeframe["60m"] == [dates[-1]]


def test_incremental_watermark_at_or_after_target_is_noop(monkeypatch):
    sessions = 60
    rows = _intraday_rows(sessions)
    daily = _daily_rows(sessions)
    dates = _session_dates(rows)
    target_date = dates[-1]
    # Already caught up through the target's last bucket -> zero writes.
    watermark = _bucket_watermark(dates[-1])

    db = _DB(
        intraday=rows,
        daily=daily,
        features=[_feature_row("15m", watermark)],
    )
    monkeypatch.setattr(intraday_flow, "SupabaseClient", lambda: db)

    total = intraday_flow.calculate_intraday_features_for_symbol(
        "SSI", timeframes=["15m"], mode="incremental", target_date=target_date
    )
    assert total == 0
    assert db.upsert_calls == []


def test_incremental_watermark_after_target_short_circuits(monkeypatch):
    sessions = 60
    rows = _intraday_rows(sessions)
    daily = _daily_rows(sessions)
    dates = _session_dates(rows)
    target_date = dates[-1]
    # watermark beyond the target day end -> the whole symbol is a no-op before
    # any source read.
    watermark = pd.Timestamp(target_date + pd.Timedelta(days=1), tz=VN_TZ).tz_convert("UTC")

    db = _DB(
        intraday=rows,
        daily=daily,
        features=[_feature_row("15m", watermark)],
    )
    monkeypatch.setattr(intraday_flow, "SupabaseClient", lambda: db)

    total = intraday_flow.calculate_intraday_features_for_symbol(
        "SSI", timeframes=["15m"], mode="incremental", target_date=target_date
    )
    assert total == 0
    assert db.upsert_calls == []
    # The short-circuit returned before reading the 1m source.
    assert not any(name == "stock_intraday" for name, *_ in db.calls)


def test_incremental_preflight_failure_leaves_zero_upserts(monkeypatch):
    """A read failure must surface before any timeframe is written."""
    sessions = 60
    rows = _intraday_rows(sessions)
    daily = _daily_rows(sessions)
    dates = _session_dates(rows)
    target_date = dates[-1]

    db = _DB(intraday=rows, daily=daily, features=[], cap=10, repeat=rows[:10])
    monkeypatch.setattr(intraday_flow, "SupabaseClient", lambda: db)

    with pytest.raises(RuntimeError, match="Repeated PostgREST page"):
        intraday_flow.calculate_intraday_features_for_symbol(
            "SSI", timeframes=["15m", "60m"], mode="incremental",
            target_date=target_date,
        )
    assert db.upsert_calls == []


def test_catchup_window_low_cap_paginates():
    sessions = 30
    rows = _intraday_rows(sessions)
    dates = _session_dates(rows)
    output_start = dates[10].isoformat() + "T00:00:00Z"
    end = (pd.Timestamp(dates[-1]) + pd.Timedelta(days=1)).isoformat() + "T00:00:00Z"

    db = _DB(intraday=rows, cap=7)
    loaded = fetch_intraday_catchup_window(
        db, "SSI", output_start, end, trading_sessions=250
    )
    assert len(loaded) == 30 * 4  # 10 warm-up sessions + 20 catch-up sessions
    assert len(db.calls) > 2  # exercised multiple capped pages


def test_incremental_is_idempotent(monkeypatch):
    sessions = 60
    rows = _intraday_rows(sessions)
    daily = _daily_rows(sessions)
    dates = _session_dates(rows)
    target_date = dates[-1]
    watermark = _bucket_watermark(dates[-4])

    def run():
        db = _DB(
            intraday=rows,
            daily=daily,
            features=[_feature_row("15m", watermark)],
        )
        monkeypatch.setattr(intraday_flow, "SupabaseClient", lambda: db)
        intraday_flow.calculate_intraday_features_for_symbol(
            "SSI", timeframes=["15m"], mode="incremental", target_date=target_date
        )
        return db.upsert_calls[0][1]

    def comparable(records):
        return [
            {key: value for key, value in record.items() if key != "last_updated_at"}
            for record in records
        ]

    first = comparable(run())
    second = comparable(run())
    assert first == second
