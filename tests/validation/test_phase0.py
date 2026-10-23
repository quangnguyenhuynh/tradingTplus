from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from copy import deepcopy
import pytest

from src.quality.validators.phase0 import check_intraday_payload, numeric_equal, reconcile_sample, verify_schema


class Result:
    def __init__(self, data, count=None): self.data, self.count = data, len(data) if count is None else count


class Query:
    WRITE_METHODS = {"insert", "upsert", "delete", "update", "rpc"}

    def __init__(self, db, table):
        self.db, self.table, self.filters, self.limit_count = db, table, [], None
        self.range_count, self.orders = None, []

    def select(self, *_args, **_kwargs): return self
    def eq(self, key, value): self.filters.append(("eq", key, value)); return self
    def gte(self, key, value): self.filters.append(("gte", key, value)); return self
    def lt(self, key, value): self.filters.append(("lt", key, value)); return self
    def order(self, field, desc=False): self.orders.append((field, desc)); return self
    def range(self, first, last): self.range_count = (first, last); return self
    def limit(self, count): self.limit_count = count; return self

    def execute(self):
        self.db.reads.append((self.table, tuple(self.filters), self.limit_count))
        rows = self.db.rows.get(self.table, [])
        def value_of(value, field):
            return datetime.fromisoformat(value.replace('Z', '+00:00')) if field == 'time' else value
        for op, key, value in self.filters:
            wanted = value_of(value, key)
            if op == "eq": rows = [row for row in rows if value_of(row.get(key), key) == wanted]
            elif op == "gte": rows = [row for row in rows if value_of(row.get(key), key) >= wanted]
            else: rows = [row for row in rows if value_of(row.get(key), key) < wanted]
        for field, descending in reversed(self.orders):
            rows = sorted(rows, key=lambda r: value_of(r.get(field, ''), field), reverse=descending)
        total = len(rows)
        if self.range_count:
            rows = rows[self.range_count[0]:self.range_count[1] + 1]
        return Result(rows[:self.limit_count] if self.limit_count else rows, total)

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
    payload = {"symbol": "SSI", "tradingDate": "03/08/2026", "open": 19, "high": 21,
               "low": 18, "close": 20, "totalMatch": 1000, "totalMatchValue": 20000, "totalDeal": 0, "totalDealValue": 0}
    return {
        "stock_raw_daily": [{"symbol": "SSI", "trading_date": "2026-08-03", "payload": payload, "source": "ssi_v3"}],
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
    assert client.reads and all(read[2] is None for read in client.reads)


def test_critical_numeric_mismatch_fails():
    result = reconcile_sample(Client(_daily_rows(feature_close=22)), symbol="SSI",
                              trading_date=date(2026, 8, 3), timeframe="1d")
    assert result["status"] == "FAIL"
    assert any(row["field"] == "close" and not row["match"] for row in result["comparisons"])


def test_missing_layer_is_unknown():
    rows = _daily_rows(); rows["stock_features"] = []
    result = reconcile_sample(Client(rows), symbol="SSI", trading_date=date(2026, 8, 3), timeframe="1d")
    assert result["status"] == "UNKNOWN"
    assert "features" in result["missing"]


class Cursor:
    def __init__(self, answers, sql): self.answers, self.index, self.sql = answers, -1, sql
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def execute(self, sql):
        assert sql.strip().lower().startswith("select")
        self.sql.append(sql)
        self.index += 1
    def fetchone(self): return self.answers[self.index]
    def fetchall(self): return self.answers[self.index]


class Connection:
    def __init__(self, answers): self.answers, self.sql = answers, []
    def cursor(self): return Cursor(self.answers, self.sql)


def test_schema_catalog_contract_passes_without_invoking_function():
    connection = Connection([
        ("jsonb", "YES", None),
        (True, ['search_path=""'], True, False, False, False),
        [("stock_features_pkey", True, True, True, True, True, ["symbol", "timeframe", "time"])],
    ])
    result = verify_schema(connection)
    assert result["status"] == "PASS"
    assert result["read_only"] is True


def schema_answers(*, payload=('jsonb', 'YES', None), function=None, indexes=None):
    return [payload, function if function is not None else (True, ['search_path=""'], True, False, False, False),
            indexes if indexes is not None else [('any_pk_name', True, True, True, True, True, ['symbol', 'timeframe', 'time'])]]


@pytest.mark.parametrize('payload', [None, ('json', 'YES', None), ('jsonb', 'NO', None), ('jsonb', 'YES', "'{}'::jsonb")])
def test_schema_payload_contract_failures(payload):
    result = verify_schema(Connection(schema_answers(payload=payload)))
    assert result['status'] == 'FAIL'
    assert result['checks'][0]['expected'] == ['jsonb', 'YES', None]
    assert result['checks'][0]['reason']


@pytest.mark.parametrize('index', [
    ('nonunique', False, True, True, True, True, ['symbol', 'timeframe', 'time']),
    ('invalid', True, False, True, True, True, ['symbol', 'timeframe', 'time']),
    ('not_ready', True, True, False, True, True, ['symbol', 'timeframe', 'time']),
    ('partial', True, True, True, False, True, ['symbol', 'timeframe', 'time']),
    ('expression', True, True, True, True, False, ['symbol', 'timeframe', 'time']),
    ('extra_key', True, True, True, True, True, ['symbol', 'timeframe', 'time', 'extra']),
    ('missing_time', True, True, True, True, True, ['symbol', 'timeframe']),
])
def test_schema_unique_contract_failures(index):
    result = verify_schema(Connection(schema_answers(indexes=[index])))
    assert result['status'] == 'FAIL' and not result['checks'][2]['matching_indexes']


@pytest.mark.parametrize('columns', [['symbol', 'timeframe', 'time'], ['time', 'symbol', 'timeframe']])
def test_schema_accepts_unique_key_without_index_name_dependency(columns):
    db = Connection(schema_answers(indexes=[('arbitrary_constraint_backing_index', True, True, True, True, True, columns)]))
    result = verify_schema(db)
    assert result['status'] == 'PASS'
    sql = '\n'.join(db.sql)
    assert "table_name='stock_raw_intraday'" in sql and "t.relname='stock_features'" in sql
    assert "table_name='raw_intraday'" not in sql and "tablename='features'" not in sql
    assert 'indnkeyatts' in sql and 'indisvalid' in sql
    assert "has_function_privilege('public'" not in sql  # PUBLIC is an ACL grantee, not a role.
    assert 'a.grantee=0' in sql and 'acldefault' in sql
    assert all('expected' in c and 'observed' in c and 'reason' in c for c in result['checks'])


@pytest.mark.parametrize('function', [
    (False, ['search_path=""'], True, False, False, False),
    (True, ['search_path=public'], True, False, False, False),
    (True, ['search_path=""'], False, False, False, False),
    (True, ['search_path=""'], True, True, False, False),
    (True, ['search_path=""'], True, False, True, False),
    (True, ['search_path=""'], True, False, False, True),
])
def test_schema_rpc_security_not_weakened(function):
    assert verify_schema(Connection(schema_answers(function=function)))['status'] == 'FAIL'


def intraday_rows(*, day='2026-10-21', minutes=('09:15:00',), value=9007199254740993):
    from src.contracts.intraday_preview import map_intraday_preview
    raws, clean = [], []
    for i, minute in enumerate(minutes):
        payload = dict(symbol='SSI', tradingDate=f"{day.replace('-', '/')} {minute}",
                       open='10', high='11', low='9', close='10.5', volume='100', value=str(value) if value is not None else None)
        mapped, reports = map_intraday_preview([payload], 'SSI', day, day, source='ssi_v3')
        assert mapped[0] is not None, reports
        clean.append(mapped[0])
        raws.append(dict(id=i, symbol='SSI', time=mapped[0]['time'], payload=payload, source='ssi_v3'))
    return {'stock_raw_intraday': raws, 'stock_intraday': clean, 'stock_features': []}


def reconcile(rows, timeframe='1m', timestamp=None, day='2026-10-21', **kwargs):
    client = Client(rows)
    result = reconcile_sample(client, symbol='SSI', trading_date=date.fromisoformat(day), timeframe=timeframe,
                              timestamp=timestamp, **kwargs)
    return result, client


def bucket_rows(timeframe='15m', minutes=('09:15:00', '09:16:00'), **kwargs):
    rows = intraday_rows(minutes=minutes, value=1001, **kwargs)
    from src.features.stock.intraday import aggregate_timeframe
    import pandas as pd
    aggregate = aggregate_timeframe(pd.DataFrame(rows['stock_intraday']), timeframe).iloc[0].to_dict()
    aggregate['time'] = aggregate['time'].isoformat()
    rows['stock_features'] = [{**aggregate, 'symbol': 'SSI', 'timeframe': timeframe}]
    return rows


@pytest.fixture(autouse=True)
def no_network_ingest_or_feature_calculation(monkeypatch):
    def fail(*a, **kw): raise AssertionError('diagnostic invoked network/ingest/feature calculation')
    import requests
    monkeypatch.setattr(requests.sessions.Session, 'request', fail)
    monkeypatch.setattr('src.providers.ssi.adapters.v3.SSIV3Adapter.preview_intraday', fail)
    monkeypatch.setattr('src.ingest.stock_intraday.manual.run_manual_intraday', fail)
    monkeypatch.setattr('src.features.stock.intraday.compute_intraday_features', fail)
    monkeypatch.setattr('src.features.stock.intraday.calculate_intraday_features_for_symbol', fail)


def test_v3_1m_passes_without_feature_and_preserves_exact_integer():
    rows = intraday_rows()
    result, client = reconcile(rows)
    assert result['status'] == 'PASS', result
    assert result['layers']['clean_to_feature']['status'] == 'NOT_APPLICABLE'
    assert not any(table == 'stock_features' for table, *_ in client.reads)
    value = next(c for c in result['comparisons'] if c['field'] == 'value')
    assert value['expected'] == value['actual'] == 9007199254740993 and value['match']
    time = next(c for c in result['comparisons'] if c['field'] == 'time')
    assert datetime.fromisoformat(time['expected'].replace('Z', '+00:00')) == datetime(2026, 10, 21, 2, 15, tzinfo=timezone.utc)
    assert result['read_only'] is True


@pytest.mark.parametrize('field,actual', [('symbol', 'HPG'), ('timeframe', '15m'), ('open', 12), ('high', 12),
    ('low', 8), ('close', 11), ('volume', 101), ('value', 9007199254740994)])
def test_v3_exact_canonical_field_mismatch(field, actual):
    rows = intraday_rows()
    if field in {'symbol', 'timeframe'}:
        # These cannot match the DB scope; exact field semantics also tested directly below.
        from src.quality.validators.phase0 import compare_fields
        compared = compare_fields({'symbol': 'SSI', 'timeframe': '1m'}, {field: actual}, (field,), 1e-6, exact_intraday=True)
        assert not compared[0]['match']
        return
    rows['stock_intraday'][0][field] = actual
    result, _ = reconcile(rows, tolerance=1e-6)
    assert result['status'] == 'FAIL'
    assert any(c['field'] == field and not c['match'] and c['actual'] == actual for c in result['comparisons'])


@pytest.mark.parametrize('field', ['volume', 'value'])
def test_integer_tolerance_never_hides_one_unit(field):
    rows = intraday_rows(); rows['stock_intraday'][0][field] += 1
    result, _ = reconcile(rows, tolerance=100)
    assert result['status'] == 'FAIL' and any(c['field'] == field and not c['match'] for c in result['comparisons'])


def test_ohlc_tolerance_and_offset_timestamp_equivalence():
    rows = intraday_rows()
    rows['stock_intraday'][0].update(time='2026-10-21T09:15:00+07:00', close=10.5000001)
    result, _ = reconcile(rows, timestamp='2026-10-21T02:15:00Z')
    assert result['status'] == 'PASS', result


@pytest.mark.parametrize('source', ['SSI', 'ssi_v2', None, 'unknown'])
def test_unsupported_legacy_source_unknown_never_remapped(source):
    rows = intraday_rows(); rows['stock_raw_intraday'][0].update(source=source, payload={'TradingDate': '21/10/2026', 'Time': '09:15:17', 'Value': 'retired'})
    result, _ = reconcile(rows)
    assert result['status'] == 'UNKNOWN'
    assert result['layers']['raw_to_clean']['diagnostics'][0]['code'] == 'SOURCE_UNSUPPORTED'
    assert not result['comparisons']


@pytest.mark.parametrize('payload,code', [(None, 'RAW_PAYLOAD_MISSING'), ({'TradingDate': '21/10/2026', 'Time': '09:15:17'}, 'SOURCE_PAYLOAD_INCOMPATIBLE')])
def test_missing_or_incompatible_payload_unknown(payload, code):
    rows = intraday_rows(); rows['stock_raw_intraday'][0]['payload'] = payload
    result, _ = reconcile(rows)
    assert result['status'] == 'UNKNOWN'
    assert any(d['code'] == code for d in result['layers']['raw_to_clean']['diagnostics'])


@pytest.mark.parametrize('clean_value,expected', [(None, 'PASS'), (0, 'FAIL')])
def test_missing_source_value_is_null_not_zero(clean_value, expected):
    rows = intraday_rows(value=None); rows['stock_intraday'][0]['value'] = clean_value
    result, _ = reconcile(rows)
    assert result['status'] == expected
    value = next(c for c in result['comparisons'] if c['field'] == 'value')
    assert value['expected'] is None


@pytest.mark.parametrize('table,code', [('stock_intraday', 'CLEAN_MISSING'), ('stock_raw_intraday', 'RAW_MISSING')])
def test_missing_exact_layer_is_unknown(table, code):
    rows = intraday_rows(); rows[table] = []
    result, _ = reconcile(rows)
    assert result['status'] == 'UNKNOWN'
    assert any(d['code'] == code for d in result['layers']['raw_to_clean']['diagnostics'])


@pytest.mark.parametrize('source', ['ssi_v3', 'SSI'])
def test_multiple_raw_versions_or_cross_source_collision_unknown(source):
    rows = intraday_rows(); other = deepcopy(rows['stock_raw_intraday'][0]); other.update(source=source, id=2)
    rows['stock_raw_intraday'].append(other)
    result, _ = reconcile(rows)
    assert result['status'] == 'UNKNOWN'
    assert result['layers']['raw_to_clean']['diagnostics'][0]['code'] == 'RAW_AMBIGUOUS'


def test_duplicate_canonical_instant_fails_without_deduplication():
    rows = intraday_rows(); other = deepcopy(rows['stock_intraday'][0]); other['time'] = '2026-10-21T09:15:00+07:00'
    rows['stock_intraday'].append(other)
    result, _ = reconcile(rows)
    assert result['status'] == 'FAIL'


def test_explicit_instant_never_selects_nearby_and_seconds_are_preserved():
    rows = intraday_rows(minutes=('09:15:17',))
    result, _ = reconcile(rows, timestamp='2026-10-21T02:15:00Z')
    assert result['status'] == 'UNKNOWN' and not result['comparisons']
    result, _ = reconcile(rows, timestamp='2026-10-21T02:15:17Z')
    assert result['status'] == 'PASS'
    assert result['selected_time'] == '2026-10-21T02:15:17+00:00'


def test_raw_identity_payload_timestamp_mismatch_fails_even_without_clean():
    rows = intraday_rows(); rows['stock_raw_intraday'][0]['time'] = '2026-10-21T02:16:00Z'; rows['stock_intraday'] = []
    result, _ = reconcile(rows)
    assert result['status'] == 'FAIL'
    assert any(c['field'] == 'time' and not c['match'] for c in result['comparisons'])


def test_default_selects_earliest_v3_instant_deterministically():
    rows = intraday_rows(minutes=('09:16:00', '09:15:00'))
    legacy = deepcopy(rows['stock_raw_intraday'][0]); legacy.update(time='2026-10-21T02:00:17Z', source='SSI')
    rows['stock_raw_intraday'].append(legacy)
    result, client = reconcile(rows)
    assert result['status'] == 'PASS' and result['selected_time'] == '2026-10-21T02:15:00+00:00'
    for _, filters, _ in client.reads:
        assert ('eq', 'symbol', 'SSI') in filters
        assert ('gte', 'time', '2026-10-20T17:00:00+00:00') in filters
        assert ('lt', 'time', '2026-10-21T17:00:00+00:00') in filters


@pytest.mark.parametrize('timeframe,minutes', [('15m', ('09:15:00', '09:29:00')),
    ('60m', ('11:00:00', '11:29:00', '11:30:00'))])
def test_observed_feature_bucket_reuses_real_aggregation_without_fixed_bar_count(timeframe, minutes):
    rows = bucket_rows(timeframe, minutes)
    result, _ = reconcile(rows, timeframe)
    assert result['status'] == 'PASS', result
    assert result['layers']['raw_to_clean']['status'] == result['layers']['clean_to_feature']['status'] == 'PASS'
    assert result['coverage_status'] == 'UNVERIFIED'


def test_lunch_and_other_dates_not_aggregated_together():
    rows = bucket_rows('60m', ('11:00:00', '11:29:00'))
    afternoon = intraday_rows(minutes=('13:00:00',), value=999999)
    tomorrow = intraday_rows(day='2026-10-22', minutes=('11:00:00',), value=999999)
    for table in ('stock_raw_intraday', 'stock_intraday'):
        rows[table].extend(afternoon[table] + tomorrow[table])
    result, _ = reconcile(rows, '60m')
    assert result['status'] == 'PASS', result
    assert next(c['expected'] for c in result['comparisons'] if c['layer'] == 'clean_to_feature' and c['field'] == 'value') == 2002


def test_exact_feature_timestamp_no_nearby_bucket():
    rows = bucket_rows()
    result, _ = reconcile(rows, '15m', timestamp='2026-10-21T02:30:00Z')
    assert result['status'] == 'UNKNOWN' and result['feature_time'] is None


def test_open_partial_bucket_unknown():
    from zoneinfo import ZoneInfo
    tomorrow = (datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date() + timedelta(days=1)).isoformat()
    rows = bucket_rows(day=tomorrow)
    result, _ = reconcile(rows, '15m', day=tomorrow)
    assert result['status'] == 'UNKNOWN'
    assert result['layers']['clean_to_feature']['diagnostics'][0]['code'] == 'BUCKET_NOT_CLOSED'


def test_missing_values_never_invoke_legacy_aggregate_estimation(monkeypatch):
    rows = bucket_rows(); rows['stock_intraday'][0]['value'] = None; rows['stock_raw_intraday'][0]['payload']['value'] = None
    def fail(*a, **kw): raise AssertionError('legacy estimate reached')
    monkeypatch.setattr('src.features.stock.intraday.aggregate_timeframe', fail)
    result, _ = reconcile(rows, '15m')
    assert result['status'] == 'UNKNOWN'
    assert result['layers']['raw_to_clean']['status'] == 'PASS'
    assert result['layers']['clean_to_feature']['diagnostics'][0]['code'] == 'AGGREGATION_EVIDENCE_MISSING'


def test_missing_raw_evidence_does_not_hide_verified_feature_mismatch():
    rows = bucket_rows(); rows['stock_raw_intraday'] = []; rows['stock_features'][0]['close'] = 99
    result, _ = reconcile(rows, '15m')
    assert result['status'] == 'FAIL'
    assert result['layers']['raw_to_clean']['status'] == 'UNKNOWN'
    assert result['layers']['clean_to_feature']['status'] == 'FAIL'


def test_unsupported_source_layer_separate_from_observed_aggregate():
    rows = bucket_rows()
    for raw in rows['stock_raw_intraday']: raw['source'] = 'SSI'
    result, _ = reconcile(rows, '15m')
    assert result['status'] == 'UNKNOWN'
    assert result['layers']['raw_to_clean']['status'] == 'UNKNOWN'
    assert result['layers']['clean_to_feature']['status'] == 'PASS'


def test_daily_legacy_source_not_remapped_but_feature_comparison_independent():
    rows = _daily_rows(); rows['stock_raw_daily'][0]['source'] = 'SSI'
    result = reconcile_sample(Client(rows), symbol='SSI', trading_date=date(2026, 8, 3), timeframe='1d')
    assert result['status'] == 'UNKNOWN' and result['layers']['clean_to_feature']['status'] == 'PASS'
    rows['stock_features'][0]['close'] = 99
    assert reconcile_sample(Client(rows), symbol='SSI', trading_date=date(2026, 8, 3), timeframe='1d')['status'] == 'FAIL'


def test_scoped_paging_count_truncation_returns_unknown():
    client = Client(intraday_rows())
    original = client.table
    def table(name):
        q = original(name); execute = q.execute
        def truncated():
            result = execute(); result.count += 1
            return result
        q.execute = truncated
        return q
    client.table = table
    result = reconcile_sample(client, symbol='SSI', trading_date=date(2026, 10, 21), timeframe='1m')
    assert result['status'] == 'UNKNOWN'
    assert result['layers']['evidence']['diagnostics'][0]['code'] == 'BOUNDED_READ_INCOMPLETE'


@pytest.mark.parametrize('timestamp,tolerance', [('2026-10-21T09:15:00', 1e-6), ('2026-10-22T02:15:00Z', 1e-6),
    (None, -1), (None, float('nan')), (None, float('inf'))])
def test_invalid_scope_rejected_before_reads(timestamp, tolerance):
    client = Client({})
    with pytest.raises(ValueError):
        reconcile_sample(client, symbol='SSI', trading_date=date(2026, 10, 21), timeframe='1m', timestamp=timestamp, tolerance=tolerance)
    assert not client.reads


def test_schema_missing_unique_identity_fails():
    assert verify_schema(Connection(schema_answers(indexes=[])))['status'] == 'FAIL'


def test_schema_missing_expected_rpc_signature_fails():
    answers = schema_answers(); answers[1] = None
    result = verify_schema(Connection(answers))
    assert result['status'] == 'FAIL' and not result['checks'][1]['exists']


@pytest.mark.parametrize('timeframe', ['15m', '60m'])
def test_higher_timeframe_feature_value_mismatch_is_exact(timeframe):
    rows = bucket_rows(timeframe)
    rows['stock_features'][0]['value'] += 1
    result, _ = reconcile(rows, timeframe, tolerance=100)
    assert result['status'] == 'FAIL'
    assert any(c['field'] == 'value' and not c['match'] and c['layer'] == 'clean_to_feature' for c in result['comparisons'])


@pytest.mark.parametrize('value', [float('nan'), float('inf'), 'invalid', True])
def test_invalid_clean_price_not_silently_dropped_by_aggregation(value):
    rows = bucket_rows(); rows['stock_intraday'][0]['open'] = value
    result, _ = reconcile(rows, '15m')
    assert result['status'] == 'FAIL'
    assert result['layers']['clean_to_feature']['diagnostics'][0]['code'] == 'INVALID_CLEAN_PRICE'


def test_full_bounded_day_paging_and_no_unrelated_scope():
    minutes = [(datetime(2026, 10, 21, 9) + timedelta(minutes=i)).strftime('%H:%M:%S') for i in range(205)]
    rows = intraday_rows(minutes=minutes)
    tomorrow = intraday_rows(day='2026-10-22')
    for table in ('stock_raw_intraday', 'stock_intraday'):
        rows[table].extend(tomorrow[table])
    result, client = reconcile(rows)
    assert result['status'] == 'PASS'
    assert sum(table == 'stock_raw_intraday' for table, *_ in client.reads) == 3
    assert sum(table == 'stock_intraday' for table, *_ in client.reads) == 3


def test_day_safety_bound_does_not_allow_partial_pass():
    rows = intraday_rows(); rows['stock_raw_intraday'] *= 3001
    result, _ = reconcile(rows)
    assert result['status'] == 'UNKNOWN' and not result['comparisons']
    assert result['layers']['evidence']['diagnostics'][0]['code'] == 'BOUNDED_READ_INCOMPLETE'
