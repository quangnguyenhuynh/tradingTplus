"""Synthetic edge cases; these are not evidence of a live SSI payload contract."""
import copy
import math
import pytest
from src.data_contracts.engine import map_record
from src.data_contracts.registry import MappingConfigurationError, get_contract, get_mapping, validate_mapping


def test_unknown_registry_coordinates_never_fallback():
    with pytest.raises(MappingConfigurationError, match="unknown source"): get_mapping("ssi_does_not_exist", "stock_daily")
    with pytest.raises(MappingConfigurationError, match="unknown source/dataset"): get_mapping("ssi_v2", "missing")
    with pytest.raises(MappingConfigurationError, match="unknown mapping version"): get_mapping("ssi_v2", "stock_daily", "9")
    with pytest.raises(MappingConfigurationError, match="unknown contract version"): get_contract("stock_daily", "9")

@pytest.mark.parametrize(("mutation", "message"), [
    (lambda m: m["fields"].update(bogus={"aliases":["X"],"transform":"float"}), "unknown target"),
    (lambda m: m["fields"]["open_price"].update(transform="eval"), "unknown transform"),
    (lambda m: m.update(contract_version="9"), "incompatible contract"),
    (lambda m: m["fields"].pop("symbol"), "required target"),
])
def test_invalid_mapping_configuration_is_rejected(mutation, message):
    mapping=copy.deepcopy(get_mapping("ssi_v2","stock_daily")); mutation(mapping)
    with pytest.raises(MappingConfigurationError, match=message): validate_mapping("ssi_v2","stock_daily",mapping)

def test_extra_fields_are_filtered_without_mutating_raw():
    raw={"IndexId":"VNINDEX","TradingDate":"25/08/2026","Surprise":7}; before=copy.deepcopy(raw)
    result=map_record("ssi_v2","index_daily",raw)
    assert result.candidate and "Surprise" not in result.candidate
    assert result.report["unused_source_fields"] == ["Surprise"] and raw == before

def test_missing_and_bad_type_are_distinct():
    missing=map_record("ssi_v2","stock_daily",{}, {"symbol":"SSI","date":"18/06/2026"})
    invalid=map_record("ssi_v2","stock_daily",{"OpenPrice":"bad"},{"symbol":"SSI","date":"18/06/2026"})
    assert "open_price" in missing.report["missing_optional"] and not missing.report["transform_errors"]
    assert invalid.candidate is None and invalid.report["transform_errors"][0]["field"] == "open_price"

@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -float("inf")])
def test_boolean_nan_and_infinity_are_not_numbers(value):
    result=map_record("ssi_v2","stock_daily",{"OpenPrice":value},{"symbol":"SSI","date":"18/06/2026"})
    assert result.candidate is None and result.report["transform_errors"]

def test_null_zero_negative_and_ssi_placeholder_rules_are_explicit():
    result=map_record("ssi_v2","stock_daily",{"RefPrice":0,"PriceChange":-2,"OpenPrice":None},{"symbol":"SSI","date":"18/06/2026"})
    assert result.candidate["ref_price"] is None and result.candidate["price_change"] == -2
    assert "open_price" in result.report["missing_optional"]

def test_equivalent_aliases_are_accepted_but_conflicts_reject():
    same=map_record("ssi_v2","stock_daily",{"OpenPrice":"10","Open":10},{"symbol":"SSI","date":"18/06/2026"})
    conflict=map_record("ssi_v2","stock_daily",{"OpenPrice":10,"Open":11},{"symbol":"SSI","date":"18/06/2026"})
    assert same.candidate["open_price"] == 10
    assert conflict.candidate is None and conflict.report["alias_conflicts"][0]["field"] == "open_price"

def test_unit_conversion_occurs_only_when_declared(monkeypatch):
    import src.data_contracts.engine as engine
    mapping=copy.deepcopy(get_mapping("ssi_v2","stock_daily")); mapping["fields"]["open_price"]["unit_multiplier"]=1000
    monkeypatch.setattr(engine,"get_mapping",lambda *a,**k:mapping)
    assert engine.map_record("ssi_v2","stock_daily",{"OpenPrice":2},{"symbol":"SSI","date":"18/06/2026"}).candidate["open_price"] == 2000

def test_bad_symbol_date_and_candle_timestamp_reject():
    assert map_record("ssi_v2","stock_daily",{}, {"symbol":"bad symbol","date":"18/06/2026"}).candidate is None
    assert map_record("ssi_v2","stock_daily",{}, {"symbol":"SSI","date":"2026.06.18"}).candidate is None
    candle=map_record("ssi_v2","stock_intraday",{"Time":"25:00:00"},{"symbol":"SSI","date":"18/06/2026"})
    assert candle.candidate is None and candle.report["transform_errors"]
