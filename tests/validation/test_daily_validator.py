from src.validation.daily_validator import validate_daily_record


def rec(**overrides):
    base = {
        "symbol": "SSI", "trading_date": "2026-07-10",
        "open_price": 10.0, "highest_price": 11.0, "lowest_price": 9.5, "close_price": 10.5,
        "ref_price": 10.0, "ceiling_price": 12.0, "floor_price": 8.0,
        "average_price": 10.2, "close_price_adjusted": 10.5,
        "price_change": 0.5, "per_price_change": 5.0,
        "total_match_vol": 100, "total_deal_vol": 20, "total_traded_vol": 120,
        "total_match_val": 1000, "total_deal_val": 200, "total_traded_value": 1200,
        "foreign_buy_vol_total": 0, "foreign_sell_vol_total": 0,
        "foreign_buy_val_total": 0, "foreign_sell_val_total": 0,
        "total_buy_trade": 1, "total_buy_trade_vol": 100, "total_sell_trade": 1, "total_sell_trade_vol": 100,
        "net_foreign_vol": -10, "net_foreign_val": -100,
    }
    base.update(overrides)
    return base


def codes(result):
    return [i.code for i in result.errors + result.warnings]


def test_valid_daily_record():
    assert validate_daily_record(rec()).is_valid


def test_missing_required_field():
    r = rec(); r.pop("close_price")
    result = validate_daily_record(r)
    assert not result.is_valid
    assert "DAILY_REQUIRED_FIELD_MISSING" in codes(result)


def test_high_below_close():
    result = validate_daily_record(rec(highest_price=10.0, close_price=10.5))
    assert not result.is_valid
    assert "DAILY_INVALID_OHLC" in codes(result)


def test_low_above_open():
    result = validate_daily_record(rec(lowest_price=10.2, open_price=10.0))
    assert not result.is_valid
    assert "DAILY_INVALID_OHLC" in codes(result)


def test_negative_price():
    result = validate_daily_record(rec(open_price=-1))
    assert not result.is_valid
    assert "DAILY_NON_POSITIVE_PRICE" in codes(result)


def test_negative_volume():
    result = validate_daily_record(rec(total_match_vol=-1))
    assert not result.is_valid
    assert "DAILY_NEGATIVE_VOLUME_OR_VALUE" in codes(result)


def test_ref_outside_floor_ceiling():
    result = validate_daily_record(rec(ref_price=13))
    assert not result.is_valid
    assert "DAILY_INVALID_PRICE_BOUNDS" in codes(result)


def test_close_above_ceiling():
    result = validate_daily_record(rec(close_price=13, highest_price=13))
    assert not result.is_valid
    assert "DAILY_PRICE_OUTSIDE_LIMIT" in codes(result)


def test_price_change_mismatch_warning():
    result = validate_daily_record(rec(price_change=0.1, per_price_change=1.0))
    assert result.is_valid
    assert "DAILY_PRICE_CHANGE_MISMATCH" in codes(result)


def test_total_volume_mismatch_warning():
    result = validate_daily_record(rec(total_traded_vol=999))
    assert result.is_valid
    assert "DAILY_TOTAL_VOLUME_MISMATCH" in codes(result)


def test_net_foreign_negative_still_valid():
    result = validate_daily_record(rec(net_foreign_vol=-999, net_foreign_val=-9999))
    assert result.is_valid


def test_warning_only_valid():
    result = validate_daily_record(rec(total_match_val=None))
    assert result.is_valid
    assert "DAILY_OPTIONAL_MARKET_FIELD_MISSING" in codes(result)
