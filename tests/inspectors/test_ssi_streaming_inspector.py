from __future__ import annotations
import pytest
from scripts.ssi_streaming_inspector.registry import STREAM_TYPES, build_channels
from scripts.ssi_streaming_inspector.output import decode_signalr_frame, inspect_arg, redact
from scripts.ssi_streaming_inspector.inspect import STATUS_CODE


def test_registry_has_six_types_and_channels():
    assert set(STREAM_TYPES) == {"securities-status","quote","trade","foreign-room","index","realtime-bar"}
    assert build_channels("quote", symbols=["ssi","hpg"]) == ["X-QUOTE:SSI","X-QUOTE:HPG"]
    assert build_channels("trade", symbols=["SSI"]) == ["X-TRADE:SSI"]
    assert build_channels("securities-status", symbols=["SSI"]) == ["F:SSI"]
    assert build_channels("foreign-room", symbols=["SSI"]) == ["R:SSI"]
    assert build_channels("index", index_codes=["vnindex"]) == ["MI:VNINDEX"]
    assert build_channels("realtime-bar", symbols=["SSI"]) == ["B:SSI"]
    assert build_channels("quote", exact_channel="X-QUOTE:ALL") == ["X-QUOTE:ALL"]


def test_signalr_frame_and_wrapper_json_string():
    frame = decode_signalr_frame('{"M":[{"H":"hub","M":"Broadcast","A":[{"DataType":"X-QUOTE","Content":"{\\"RType\\":\\"QUOTE\\",\\"Symbol\\":\\"SSI\\",\\"Time\\":\\"10:00:00\\",\\"BidPrice1\\":1,\\"BidVol1\\":2,\\"AskPrice10\\":3,\\"AskVol10\\":4}"}]}]}')
    assert frame["top_level_keys"] == ["M"]
    arg = frame["messages"][0]["args"][0]
    out = inspect_arg(arg, "quote", "X-QUOTE:SSI", 1, frame)
    assert out["data_type"] == "X-QUOTE"
    assert out["rtype"] == "QUOTE"
    assert out["symbol"] == "SSI"
    assert "BidPrice1" in out["content_keys"]
    assert "AskVol10" in out["content_keys"]


@pytest.mark.parametrize("kind,payload,field", [
    ("trade", {"DataType":"X-TRADE","Content":{"RType":"TRADE","Symbol":"SSI","TradingTime":"10:01"}}, "symbol"),
    ("securities-status", {"datatype":"F","content":{"Rtype":"F","Symbol":"SSI","Time":"09:00"}}, "symbol"),
    ("foreign-room", {"DataType":"R","Content":{"RType":"R","Symbol":"SSI","FBuyVol":1}}, "symbol"),
    ("index", {"DataType":"MI","Content":{"RType":"MI","IndexID":"VNINDEX","Time":"10:02"}}, "index_id"),
    ("realtime-bar", {"DataType":"B","Content":{"RType":"B","Symbol":"SSI","Open":1,"High":2,"Low":1,"Close":2,"Volume":10}}, "symbol"),
])
def test_type_detection_casing(kind, payload, field):
    out = inspect_arg(payload, kind, "ch", 1, {})
    assert out[field]


def test_malformed_and_redaction_and_status_codes():
    bad = decode_signalr_frame('not-json connectionToken=abc Bearer secret')
    assert bad["malformed"] is True
    safe = redact({"ConnectionToken":"abc", "headers":{"Authorization":"Bearer secret", "Cookie":"x"}, "url":"?connectionToken=abc"})
    text = str(safe)
    assert "abc" not in text and "secret" not in text
    assert STATUS_CODE["EMPTY"] == 0 and STATUS_CODE["PARTIAL"] == 2 and STATUS_CODE["FAILED"] == 1


def test_package_has_no_write_or_supabase_imports():
    import pathlib
    root = pathlib.Path("scripts/ssi_streaming_inspector")
    text = "\n".join(p.read_text() for p in root.glob("*.py"))
    assert "SupabaseClient" not in text
    assert "--write" not in text
    assert ".upsert(" not in text and "supabase.table" not in text
