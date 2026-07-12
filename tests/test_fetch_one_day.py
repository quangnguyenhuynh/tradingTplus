from datetime import datetime
from zoneinfo import ZoneInfo
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import importlib

fod = importlib.import_module("src.pipeline.fetch_one_day")


class _SSI:
    def __init__(self, daily=None, candles=None):
        self.daily = daily
        self.candles = candles

    def get_daily_price(self, symbol, date):
        return self.daily

    def get_intraday(self, symbol, date):
        return self.candles


class _DB:
    def __init__(self):
        self.raw_records = None
        self.clean_records = None
        self.raw_daily_records = None
        self.stock_daily_records = None

    def upsert_raw_daily(self, records):
        self.raw_daily_records = records

    def upsert_stock_daily(self, records):
        self.stock_daily_records = records

    def upsert_raw(self, records):
        self.raw_records = records

    def upsert_intraday(self, records):
        self.clean_records = records


def _daily():
    return {
        'RefPrice': '10.1',
        'CeilingPrice': '11.1',
        'FloorPrice': '9.0',
        'OpenPrice': '10.2',
        'HighestPrice': '10.8',
        'LowestPrice': '9.8',
        'ClosePrice': '10.5',
        'TotalMatchVol': '200',
        'TotalMatchVal': '2100',
        'TotalTradedVol': '200',
        'TotalTradedValue': '2100',
    }


def _candle(
    time='09:15:00',
    volume='100',
    value='1000',
    open_price='10',
    high='11',
    low='9',
    close='10.5',
):
    return {
        'Time': time,
        'Open': open_price,
        'High': high,
        'Low': low,
        'Close': close,
        'Volume': volume,
        'Value': value,
    }


def test_parse_time_returns_datetime_or_none():
    assert fod.parse_time('18/06/2026', '09:15:00') == datetime(2026, 6, 18, 2, 15, tzinfo=ZoneInfo('UTC'))
    assert fod.parse_time('18/06/2026', 'bad') is None


def test_build_intraday_records_skips_bad_time_and_uses_candle_volume_for_value():
    candles = [
        _candle('09:15:00', '100'),
        _candle('bad', '120'),
        _candle('09:16:00', '90'),
        _candle('09:17:00', '130'),
    ]

    raw_records, clean_records = fod.build_intraday_records('SSI', '18/06/2026', _daily(), candles)

    assert len(raw_records) == 3
    assert len(clean_records) == 3
    assert [record['value'] for record in clean_records] == [1050, 945, 1365]
    assert all(type(record['value']) is int for record in clean_records)
    assert raw_records[0]['time'] == '2026-06-18T02:15:00Z'
    assert clean_records[0]['timeframe'] == '1m'
    assert clean_records[0]['reference_price'] == 10.1
    assert 'data_hash' in raw_records[0]



def test_build_intraday_records_converts_vietnam_time_to_utc_z():
    raw_records, clean_records = fod.build_intraday_records('SSI', '05/07/2024', _daily(), [_candle('14:45:01')])

    assert raw_records[0]['time'] == '2024-07-05T07:45:01Z'
    assert clean_records[0]['time'] == '2024-07-05T07:45:01Z'
    assert fod.parse_time('05/07/2024', '14:45:01') == datetime(2024, 7, 5, 7, 45, 1, tzinfo=ZoneInfo('UTC'))


def test_build_intraday_records_ignores_api_value_and_uses_close_times_volume():
    candles = [
        _candle('09:15:00', volume='100', value='10.5', high='12', low='9', close='10.5'),
        _candle('09:16:00', volume='150', value='11', high='13', low='10', close='12'),
    ]

    raw_records, clean_records = fod.build_intraday_records('SSI', '18/06/2026', _daily(), candles)

    assert raw_records[1]['close'] == 12
    assert clean_records[1]['value'] == 1800
    assert type(clean_records[1]['value']) is int
    assert clean_records[1]['value'] != int(candles[1]['Value'])


def test_build_intraday_records_sets_value_null_when_close_or_volume_missing():
    candles = [
        _candle('09:15:00', volume='', close='10.5'),
        _candle('09:16:00', volume='100', close=''),
        _candle('09:17:00', volume='0', close='10.5'),
    ]

    _raw_records, clean_records = fod.build_intraday_records('SSI', '18/06/2026', _daily(), candles)

    assert [record['value'] for record in clean_records] == [None, None, 0]
    assert type(clean_records[2]['value']) is int
    assert [record['volume'] for record in clean_records] == [None, 100, 0]


def test_build_intraday_records_logs_normalized_debug_sample(caplog):
    caplog.set_level('DEBUG', logger='src.pipeline.fetch_one_day')

    fod.build_intraday_records('SSI', '18/06/2026', _daily(), [_candle('09:15:00', volume='100', close='10.5')])

    assert 'Normalized intraday sample rows for SSI 18/06/2026' in caplog.text
    assert "'value': 1050" in caplog.text
    assert "'value_type': 'int'" in caplog.text


def test_save_intraday_records_returns_clean_record_count():
    db = _DB()
    raw_records = [{'symbol': 'SSI'}]
    clean_records = [{'symbol': 'SSI'}, {'symbol': 'SSI'}]

    assert fod.save_intraday_records(db, raw_records, clean_records) == 2
    assert db.raw_records == raw_records
    assert db.clean_records == clean_records


def test_fetch_one_day_with_clients_returns_zero_without_daily():
    db = _DB()
    assert fod.fetch_one_day_with_clients(_SSI(daily=None, candles=[_candle()]), db, 'SSI', '18/06/2026') == 0
    assert db.raw_records is None
    assert db.clean_records is None


def test_fetch_one_day_with_clients_returns_zero_without_intraday():
    db = _DB()
    assert fod.fetch_one_day_with_clients(_SSI(daily=_daily(), candles=[]), db, 'SSI', '18/06/2026') == 0
    assert db.raw_records is None
    assert db.clean_records is None
    assert db.raw_daily_records is not None
    assert db.stock_daily_records is not None


def test_fetch_one_day_with_clients_saves_and_returns_int():
    db = _DB()
    count = fod.fetch_one_day_with_clients(
        _SSI(daily=_daily(), candles=[_candle('09:15:00'), _candle('09:16:00')]),
        db,
        'SSI',
        '18/06/2026',
    )

    assert count == 2
    assert isinstance(count, int)
    assert len(db.raw_records) == len(db.clean_records) == 2
