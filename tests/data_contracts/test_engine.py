"""Synthetic edge cases; these are not evidence of a live SSI payload contract."""
import copy
import math
import pytest
from src.contracts.engine import map_record as _map_record

def map_record(source, dataset, raw, context=None):
    if dataset == "stock_daily":
        raw = {"summary.symbol": "SSI", "summary.tradingDate": "18/06/2026", **raw}
    return _map_record(source, dataset, raw, context)
from src.contracts.registry import MappingConfigurationError, get_contract, get_mapping, validate_mapping


def test_unknown_registry_coordinates_never_fallback():
    with pytest.raises(MappingConfigurationError, match="unknown source"): get_mapping("ssi_does_not_exist", "stock_daily")
    with pytest.raises(MappingConfigurationError, match="unknown source/dataset"): get_mapping("ssi_v3", "missing")
    with pytest.raises(MappingConfigurationError, match="unknown mapping version"): get_mapping("ssi_v3", "stock_daily", "9")
    with pytest.raises(MappingConfigurationError, match="unknown contract version"): get_contract("stock_daily", "9")

@pytest.mark.parametrize(("mutation", "message"), [
    (lambda m: m["fields"].update(bogus={"aliases":["X"],"transform":"float"}), "unknown target"),
    (lambda m: m["fields"]["open_price"].update(transform="eval"), "unknown transform"),
    (lambda m: m.update(contract_version="9"), "incompatible contract"),
    (lambda m: m["fields"].pop("symbol"), "required target"),
])
def test_invalid_mapping_configuration_is_rejected(mutation, message):
    mapping=copy.deepcopy(get_mapping("ssi_v3","stock_daily")); mutation(mapping)
    with pytest.raises(MappingConfigurationError, match=message): validate_mapping("ssi_v3","stock_daily",mapping)

def test_extra_fields_are_filtered_without_mutating_raw():
    raw={"indexSummary.tradingDate":"25/08/2026","Surprise":7}; before=copy.deepcopy(raw)
    result=map_record("ssi_v3","index_daily",raw,{"index":"VNINDEX"})
    assert result.candidate and "Surprise" not in result.candidate
    assert result.report["unused_source_fields"] == ["Surprise"] and raw == before

def test_missing_and_bad_type_are_distinct():
    missing=map_record("ssi_v3","stock_daily",{}, {})
    invalid=map_record("ssi_v3","stock_daily",{"summary.open":"bad"},{})
    assert "open_price" in missing.report["missing_optional"] and not missing.report["transform_errors"]
    assert invalid.candidate is None and invalid.report["transform_errors"][0]["field"] == "open_price"

@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -float("inf")])
def test_boolean_nan_and_infinity_are_not_numbers(value):
    result=map_record("ssi_v3","stock_daily",{"summary.open":value},{})
    assert result.candidate is None and result.report["transform_errors"]

def test_null_zero_negative_and_ssi_placeholder_rules_are_explicit():
    result=map_record("ssi_v3","stock_daily",{"summary.refPrice":0,"summary.priceChange":-2,"summary.open":None},{})
    assert result.candidate["ref_price"] is None and result.candidate["price_change"] == -2
    assert "open_price" in result.report["missing_optional"]


def test_unit_conversion_occurs_only_when_declared(monkeypatch):
    import src.contracts.engine as engine
    mapping=copy.deepcopy(get_mapping("ssi_v3","stock_daily")); mapping["fields"]["open_price"]["unit_multiplier"]=1000
    monkeypatch.setattr(engine,"get_mapping",lambda *a,**k:mapping)
    assert map_record("ssi_v3","stock_daily",{"summary.open":2},{}).candidate["open_price"] == 2000



def test_equivalent_v3_aliases_are_accepted_but_conflicts_reject():
    same = map_record("ssi_v3", "stock_daily", {"summary.average": "10", "summary.averagePrice": 10})
    conflict = map_record("ssi_v3", "stock_daily", {"summary.average": 10, "summary.averagePrice": 11})
    assert same.candidate["average_price"] == 10
    assert conflict.candidate is None
    assert conflict.report["alias_conflicts"][0]["field"] == "average_price"


def test_v3_identity_and_date_are_not_repaired_from_context():
    bad_symbol = map_record("ssi_v3", "stock_daily", {"summary.symbol": "bad symbol"})
    bad_date = map_record("ssi_v3", "stock_daily", {"summary.tradingDate": "2026.06.18"})
    assert bad_symbol.candidate is None and bad_date.candidate is None
