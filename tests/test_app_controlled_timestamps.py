from datetime import datetime, timezone

from src.database.client import SupabaseClient
from src.utils.time_utils import utc_now, utc_now_iso


class _Query:
    def __init__(self, calls, table, records, options):
        self.calls = calls
        self.table = table
        self.records = records
        self.options = options

    def execute(self):
        self.calls.append((self.table, self.records, self.options))
        return object()


class _Postgrest:
    def __init__(self):
        self.calls = []

    def table(self, table):
        parent = self

        class _Table:
            def upsert(self, records, **options):
                return _Query(parent.calls, table, records, options)

        return _Table()


def _db():
    db = object.__new__(SupabaseClient)
    db.client = _Postgrest()
    return db


def test_utc_clock_is_timezone_aware_and_parseable():
    now = utc_now()
    parsed = datetime.fromisoformat(utc_now_iso())
    assert now.tzinfo is not None
    assert now.utcoffset().total_seconds() == 0
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_timestamp_stamping_copies_input_and_preserves_source_fields():
    source = {"symbol": "SSI", "time": "2026-07-24T02:00:00Z", "trading_date": "2026-07-24"}
    stamped = SupabaseClient._stamp_write_timestamps(
        "stock_daily", [source], "2026-07-24T12:00:00+00:00"
    )

    assert source == {"symbol": "SSI", "time": "2026-07-24T02:00:00Z", "trading_date": "2026-07-24"}
    assert stamped[0]["created_at"] == "2026-07-24T12:00:00+00:00"
    assert stamped[0]["updated_at"] == "2026-07-24T12:00:00+00:00"
    assert stamped[0]["time"] == source["time"]
    assert stamped[0]["trading_date"] == source["trading_date"]


def test_created_at_upsert_is_insert_then_update_without_created_at():
    db = _db()
    source = {"symbol": "SSI", "trading_date": "2026-07-24", "close_price": 25}

    db.upsert_stock_daily([source])

    assert source == {"symbol": "SSI", "trading_date": "2026-07-24", "close_price": 25}
    insert_call, update_call = db.client.calls
    assert insert_call[2]["ignore_duplicates"] is True
    assert insert_call[1][0]["created_at"]
    assert insert_call[1][0]["updated_at"]
    assert "created_at" not in update_call[1][0]
    assert update_call[1][0]["updated_at"] == insert_call[1][0]["updated_at"]


def test_table_specific_timestamps_are_app_controlled():
    stamp = "2026-07-24T12:00:00+00:00"
    cases = {
        "raw_daily": "created_at",
        "raw_intraday": "fetched_at",
        "securities": "updated_at",
        "indexes": "updated_at",
        "index_components": "updated_at",
        "foreign_trading": "updated_at",
        "orderbook_snapshot": "updated_at",
        "stream_raw_snapshot": "received_at",
        "stream_quote_snapshot": "created_at",
        "stream_trade_snapshot": "created_at",
        "stream_foreign_snapshot": "created_at",
        "stream_index_snapshot": "created_at",
        "stream_status_snapshot": "created_at",
        "stream_bar_snapshot": "created_at",
        "features": "last_updated_at",
        "data_quality_logs": "created_at",
    }
    for table, field in cases.items():
        assert SupabaseClient._stamp_write_timestamps(table, [{"value": 1}], stamp)[0][field] == stamp


def test_feature_wrapper_stamps_missing_last_updated_at():
    db = _db()
    source = {"symbol": "SSI", "timeframe": "1m", "time": "2026-07-24T02:00:00Z"}
    db.upsert_features([source])
    assert source.get("last_updated_at") is None
    assert datetime.fromisoformat(db.client.calls[0][1][0]["last_updated_at"]).tzinfo == timezone.utc
