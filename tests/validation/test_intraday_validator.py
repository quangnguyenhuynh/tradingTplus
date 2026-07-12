from src.validation.intraday_validator import validate_intraday_batch, validate_intraday_record


def candle(time="2026-07-10T02:00:00Z", **overrides):
    base = {
        "symbol": "SSI", "time": time, "timeframe": "1m",
        "open": 10, "high": 11, "low": 9, "close": 10.5,
        "volume": 100, "value": 1050, "floor_price": 8, "ceiling_price": 12,
    }
    base.update(overrides)
    return base


def daily(**overrides):
    base = {"close_price": 10.5, "total_match_vol": 200}
    base.update(overrides)
    return base


def codes(result):
    return [i.code for i in result.errors + result.warnings]


def test_valid_candle():
    assert validate_intraday_record(candle()).is_valid


def test_missing_timestamp():
    r = candle(); r.pop("time")
    result = validate_intraday_record(r)
    assert not result.is_valid
    assert "INTRADAY_REQUIRED_FIELD_MISSING" in codes(result)


def test_invalid_timeframe():
    result = validate_intraday_record(candle(timeframe="5m"))
    assert not result.is_valid
    assert "INTRADAY_INVALID_TIMEFRAME" in codes(result)


def test_high_below_open():
    result = validate_intraday_record(candle(high=9.5))
    assert not result.is_valid
    assert "INTRADAY_INVALID_OHLC" in codes(result)


def test_low_above_close():
    result = validate_intraday_record(candle(low=10.8))
    assert not result.is_valid
    assert "INTRADAY_INVALID_OHLC" in codes(result)


def test_negative_volume():
    result = validate_intraday_record(candle(volume=-1))
    assert not result.is_valid
    assert "INTRADAY_NEGATIVE_VOLUME" in codes(result)


def test_price_above_ceiling():
    result = validate_intraday_record(candle(high=13))
    assert not result.is_valid
    assert "INTRADAY_PRICE_OUTSIDE_LIMIT" in codes(result)


def test_bad_timestamp():
    result = validate_intraday_record(candle(time="bad"))
    assert not result.is_valid
    assert "INTRADAY_INVALID_TIMESTAMP" in codes(result)


def test_null_value_valid():
    assert validate_intraday_record(candle(value=None)).is_valid


def test_batch_warning_does_not_make_record_invalid():
    assert validate_intraday_record(candle(time="2026-07-10T01:00:00Z")).is_valid


def test_valid_batch():
    result = validate_intraday_batch([candle(), candle("2026-07-10T02:01:00Z")], daily_record=daily())
    assert result.is_valid


def test_duplicate_timestamp():
    result = validate_intraday_batch([candle(), candle()])
    assert not result.is_valid
    assert "INTRADAY_DUPLICATE_TIMESTAMP" in codes(result)


def test_unsorted_input():
    result = validate_intraday_batch([candle("2026-07-10T02:01:00Z"), candle("2026-07-10T02:00:00Z")])
    assert result.is_valid
    assert "INTRADAY_UNSORTED_INPUT" in codes(result)


def test_missing_minute_between_session():
    result = validate_intraday_batch([candle(), candle("2026-07-10T02:02:00Z")])
    assert result.is_valid
    assert "INTRADAY_MISSING_INTERVAL" in codes(result)


def test_lunch_break_not_missing_interval():
    # 11:30 VN is 04:30 UTC; 13:00 VN is 06:00 UTC.
    result = validate_intraday_batch([candle("2026-07-10T04:30:00Z"), candle("2026-07-10T06:00:00Z")])
    assert "INTRADAY_MISSING_INTERVAL" not in codes(result)


def test_outside_trading_session_warning():
    result = validate_intraday_batch([candle("2026-07-10T01:00:00Z")])
    assert result.is_valid
    assert "INTRADAY_OUTSIDE_TRADING_SESSION" in codes(result)


def test_daily_close_mismatch_warning():
    result = validate_intraday_batch([candle(close=10.5), candle("2026-07-10T02:01:00Z", close=10.7)], daily_record=daily(close_price=10.5))
    assert result.is_valid
    assert "INTRADAY_DAILY_CLOSE_MISMATCH" in codes(result)


def test_daily_volume_mismatch_warning():
    result = validate_intraday_batch([candle(), candle("2026-07-10T02:01:00Z")], daily_record=daily(total_match_vol=999))
    assert result.is_valid
    assert "INTRADAY_DAILY_VOLUME_MISMATCH" in codes(result)


def test_empty_batch_warning():
    result = validate_intraday_batch([])
    assert result.is_valid
    assert "INTRADAY_EMPTY_BATCH" in codes(result)


def test_duplicate_batch_invalid():
    assert not validate_intraday_batch([candle(), candle()]).is_valid
