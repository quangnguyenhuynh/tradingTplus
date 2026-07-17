from src.pipeline.streaming_snapshot import build_bar_snapshot_record, build_foreign_snapshot_record, build_quote_snapshot_record, build_raw_stream_record
from src.validation.streaming_validator import validate_stream_record


def test_missing_source_timestamp_not_replaced_with_now():
    raw = build_raw_stream_record("X-QUOTE:SSI", {"RType": "QUOTE", "Symbol": "SSI"})
    assert raw["time"] is None
    assert raw["source_time"] is None
    assert raw["received_at"] is not None


def test_quote_missing_depth_does_not_create_fake_imbalance():
    rec = build_quote_snapshot_record({"RType": "QUOTE", "Symbol": "SSI", "TradingDate": "2026-07-17", "Time": "10:00:00", "LastPrice": 10})
    assert rec["total_bid_depth_10"] is None
    assert rec["total_ask_depth_10"] is None
    assert rec["orderbook_imbalance"] is None
    assert rec["pressure_score"] is None
    assert validate_stream_record(rec, "X-QUOTE").is_valid


def test_negative_depth_is_error():
    rec = build_quote_snapshot_record({"RType": "QUOTE", "Symbol": "SSI", "TradingDate": "2026-07-17", "Time": "10:00:00", "BidVol1": -1})
    result = validate_stream_record(rec, "X-QUOTE")
    assert not result.is_valid
    assert any(i.field == "bid_vol_1" for i in result.errors)


def test_foreign_net_requires_both_operands():
    rec = build_foreign_snapshot_record({"RType": "R", "Symbol": "SSI", "TradingDate": "2026-07-17", "Time": "10:00:00", "FBuyVol": 10})
    assert rec["net_foreign_vol"] is None


def test_invalid_bar_ohlc_is_error():
    rec = build_bar_snapshot_record({"RType": "B", "Symbol": "SSI", "TradingDate": "2026-07-17", "Time": "10:00:00", "Open": 10, "High": 9, "Low": 8, "Close": 10, "Volume": 1})
    result = validate_stream_record(rec, "B")
    assert not result.is_valid
    assert any(i.code == "STREAM_INVALID_OHLC" for i in result.errors)
