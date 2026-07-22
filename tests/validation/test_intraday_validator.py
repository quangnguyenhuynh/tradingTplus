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


def missing_minutes(result):
    return sum(
        issue.actual_value["missing_minutes"]
        for issue in result.warnings
        if issue.code == "INTRADAY_MISSING_INTERVAL"
    )


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


def test_unsorted_input_is_sorted_for_gap_validation():
    result = validate_intraday_batch([
        candle("2026-07-10T02:02:21Z"),
        candle("2026-07-10T02:00:18Z"),
    ])
    assert "INTRADAY_UNSORTED_INPUT" in codes(result)
    assert missing_minutes(result) == 1


def test_missing_minute_between_session():
    result = validate_intraday_batch([candle(), candle("2026-07-10T02:02:00Z")])
    assert result.is_valid
    assert "INTRADAY_MISSING_INTERVAL" in codes(result)


def test_lunch_break_boundaries_not_missing_interval():
    result = validate_intraday_batch([
        candle("2026-07-10T04:29:47Z"),
        candle("2026-07-10T04:30:08Z"),
        candle("2026-07-10T06:00:39Z"),
    ])
    assert "INTRADAY_MISSING_INTERVAL" not in codes(result)


def test_atc_boundaries_not_missing_interval():
    result = validate_intraday_batch([
        candle("2026-07-10T07:29:51Z"),
        candle("2026-07-10T07:30:09Z"),
        candle("2026-07-10T07:45:00Z"),
    ])
    assert "INTRADAY_MISSING_INTERVAL" not in codes(result)


def test_second_offsets_in_same_minute_buckets_do_not_create_false_gap():
    result = validate_intraday_batch([
        candle("2026-07-10T02:00:58Z"),
        candle("2026-07-10T02:01:02Z"),
    ])
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

def test_missing_minute_inside_morning_session():
    result = validate_intraday_batch([candle("2026-07-10T04:27:15Z"), candle("2026-07-10T04:29:42Z")])
    assert missing_minutes(result) == 1


def test_missing_minute_inside_afternoon_session():
    result = validate_intraday_batch([candle("2026-07-10T06:00:15Z"), candle("2026-07-10T06:02:42Z")])
    assert missing_minutes(result) == 1


def test_gap_crossing_lunch_counts_only_continuous_session_minutes():
    result = validate_intraday_batch([candle("2026-07-10T04:28:00Z"), candle("2026-07-10T06:02:00Z")])
    assert missing_minutes(result) == 3  # 11:29, 13:00, and 13:01; lunch is excluded.


def test_gap_across_trading_dates_not_counted_as_same_session_gap():
    result = validate_intraday_batch([candle("2026-07-10T08:00:00Z"), candle("2026-07-13T02:00:00Z")])
    assert "INTRADAY_MISSING_INTERVAL" not in codes(result)
