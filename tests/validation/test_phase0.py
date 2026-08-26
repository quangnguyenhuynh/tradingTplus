from __future__ import annotations

from datetime import date

from src.validation.phase0 import check_intraday_payload, numeric_equal, reconcile_sample, verify_schema


class Result:
    def __init__(self, data): self.data = data


class Query:
    WRITE_METHODS = {"insert", "upsert", "delete", "update", "rpc"}

    def __init__(self, db, table):
        self.db, self.table, self.filters, self.limit_count = db, table, [], None

    def select(self, *_args): return self
    def eq(self, key, value): self.filters.append(("eq", key, value)); return self
    def gte(self, key, value): self.filters.append(("gte", key, value)); return self
    def lt(self, key, value): self.filters.append(("lt", key, value)); return self
    def order(self, *_args, **_kwargs): return self
    def limit(self, count): self.limit_count = count; return self

    def execute(self):
        self.db.reads.append((self.table, tuple(self.filters), self.limit_count))
        rows = self.db.rows.get(self.table, [])
        for op, key, value in self.filters:
            if op == "eq": rows = [row for row in rows if row.get(key) == value]
            elif op == "gte": rows = [row for row in rows if row.get(key) >= value]
            else: rows = [row for row in rows if row.get(key) < value]
        return Result(rows[:self.limit_count] if self.limit_count else rows)

    def __getattr__(self, name):
        if name in self.WRITE_METHODS:
            raise AssertionError(f"write method called: {name}")
        raise AttributeError(name)


class Client:
    def __init__(self, rows): self.rows, self.reads = rows, []
    def table(self, table): return Query(self, table)
    def rpc(self, *_args, **_kwargs): raise AssertionError("RPC must not be called")


def test_payload_historical_null_rows_do_not_fail_when_new_sample_exists():
    client = Client({"stock_raw_intraday": [
        {"symbol": "SSI", "time": "2026-08-03T02:00:00+00:00", "payload": None, "fetched_at": "old"},
        {"symbol": "SSI", "time": "2026-08-03T02:01:00+00:00", "payload": {"Time": "09:01:00"}, "fetched_at": "new"},
    ]})
    result = check_intraday_payload(client, symbol="SSI", trading_date=date(2026, 8, 3))
    assert result["status"] == "PASS"
    assert result["historical_null_rows"] == 1
    assert result["historical_null_policy"] == "EXPECTED_NO_BACKFILL"


def test_payload_missing_post_migration_sample_is_unknown_not_pass():
    result = check_intraday_payload(Client({"stock_raw_intraday": [
        {"symbol": "SSI", "time": "2026-08-03T02:00:00+00:00", "payload": None, "fetched_at": "old"},
    ]}), symbol="SSI", trading_date=date(2026, 8, 3))
    assert result["status"] == "UNKNOWN"


def _daily_rows(feature_close=20.0):
    payload = {"Symbol": "SSI", "TradingDate": "03/08/2026", "OpenPrice": 19, "HighestPrice": 21,
               "LowestPrice": 18, "ClosePrice": 20, "TotalTradedVol": 1000, "TotalTradedValue": 20000}
    return {
        "stock_raw_daily": [{"symbol": "SSI", "trading_date": "2026-08-03", "payload": payload}],
        "stock_daily": [{"symbol": "SSI", "trading_date": "2026-08-03", "open_price": 19.0,
                         "highest_price": 21.0, "lowest_price": 18.0, "close_price": 20.0,
                         "total_traded_vol": 1000.0, "total_traded_value": 20000.0}],
        "stock_features": [{"symbol": "SSI", "timeframe": "1d", "time": "2026-08-02T17:00:00+00:00",
                      "open": 19.0, "high": 21.0, "low": 18.0, "close": feature_close,
                      "volume": 1000, "value": 20000}],
    }


def test_numeric_tolerance_and_matching_reconciliation_pass_read_only():
    assert numeric_equal(20, 20.0000005, 1e-6)
    client = Client(_daily_rows(feature_close=20.0000005))
    result = reconcile_sample(client, symbol="ssi", trading_date=date(2026, 8, 3), timeframe="1d")
    assert result["status"] == "PASS"
    assert client.reads and all(read[2] == 1 for read in client.reads)


def test_critical_numeric_mismatch_fails():
    result = reconcile_sample(Client(_daily_rows(feature_close=22)), symbol="SSI",
                              trading_date=date(2026, 8, 3), timeframe="1d")
    assert result["status"] == "FAIL"
    assert any(row["field"] == "close" and not row["match"] for row in result["comparisons"])


def test_missing_layer_is_unknown():
    rows = _daily_rows(); rows["stock_features"] = []
    result = reconcile_sample(Client(rows), symbol="SSI", trading_date=date(2026, 8, 3), timeframe="1d")
    assert result["status"] == "UNKNOWN"
    assert result["missing"] == ["features"]


class Cursor:
    def __init__(self, answers): self.answers, self.index = answers, -1
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def execute(self, _sql): self.index += 1
    def fetchone(self): return self.answers[self.index]
    def fetchall(self): return self.answers[self.index]


class Connection:
    def __init__(self, answers): self.answers = answers
    def cursor(self): return Cursor(self.answers)


def test_schema_catalog_contract_passes_without_invoking_function():
    connection = Connection([
        ("jsonb", "YES", None),
        (True, ['search_path=""'], True, False, False, False),
        [("features_symbol_timeframe_time_uidx", "CREATE UNIQUE INDEX x ON public.features USING btree (symbol, timeframe, time)")],
    ])
    result = verify_schema(connection)
    assert result["status"] == "PASS"
    assert result["read_only"] is True
