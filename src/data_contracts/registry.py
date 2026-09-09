"""Load and validate immutable JSON contract/mapping declarations."""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
from typing import Any
import math
from .transforms import TRANSFORMS

ROOT = Path(__file__).parent
class MappingConfigurationError(ValueError): pass

def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle: return json.load(handle)

@lru_cache(maxsize=1)
def _contracts() -> dict[str, Any]: return _load(ROOT / "definitions.json")["datasets"]
@lru_cache(maxsize=8)
def _source(source_id: str) -> dict[str, Any]:
    path = ROOT / "mappings" / f"{source_id}.json"
    if not path.is_file(): raise MappingConfigurationError(f"unknown source: {source_id}")
    return _load(path)

def get_contract(dataset: str, contract_version: str | None = None) -> dict[str, Any]:
    try: contract = _contracts()[dataset]
    except KeyError as exc: raise MappingConfigurationError(f"unknown dataset: {dataset}") from exc
    if contract_version is not None and contract["contract_version"] != contract_version:
        raise MappingConfigurationError(f"unknown contract version: {dataset}/{contract_version}")
    return contract

def get_mapping(source_id: str, dataset: str, mapping_version: str | None = None) -> dict[str, Any]:
    source = _source(source_id)
    if source.get("source_id") != source_id: raise MappingConfigurationError("source_id does not match mapping filename")
    try: mapping = source["datasets"][dataset]
    except KeyError as exc: raise MappingConfigurationError(f"unknown source/dataset: {source_id}/{dataset}") from exc
    if mapping_version is not None and mapping["mapping_version"] != mapping_version:
        raise MappingConfigurationError(f"unknown mapping version: {source_id}/{dataset}/{mapping_version}")
    validate_mapping(source_id, dataset, mapping)
    return mapping

def validate_mapping(source_id: str, dataset: str, mapping: dict[str, Any]) -> None:
    contract = get_contract(dataset)
    if mapping.get("contract_version") != contract["contract_version"]: raise MappingConfigurationError("incompatible contract_version")
    fields = mapping.get("fields")
    if not isinstance(fields, dict): raise MappingConfigurationError("mapping fields must be an object")
    unknown = set(fields) - set(contract["fields"])
    if unknown: raise MappingConfigurationError(f"unknown target field(s): {sorted(unknown)}")
    missing = {name for name, spec in contract["fields"].items() if spec["required"]} - set(fields)
    if missing: raise MappingConfigurationError(f"required target field(s) not mapped: {sorted(missing)}")
    for target, rule in fields.items():
        if not isinstance(rule, dict): raise MappingConfigurationError(f"invalid rule for {target}")
        if rule.get("unsupported"):
            if not rule.get("reason"): raise MappingConfigurationError(f"unsupported field needs a reason: {target}")
            continue
        aliases = rule.get("aliases", [])
        if not isinstance(aliases, list) or len(aliases) != len(set(a.casefold() for a in aliases)):
            raise MappingConfigurationError(f"duplicate or invalid aliases for {target}")
        transform = rule.get("transform")
        if transform not in TRANSFORMS: raise MappingConfigurationError(f"unknown transform for {target}: {transform}")
        if not aliases and "context" not in rule and "constant" not in rule and not rule.get("unsupported"): raise MappingConfigurationError(f"no source for {target}")
        if not rule.get("unsupported") and sum(k in rule for k in ("context", "constant")) + bool(aliases) != 1: raise MappingConfigurationError(f"conflicting sources for {target}")
        multiplier = rule.get("unit_multiplier", 1)
        if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)) or not math.isfinite(multiplier):
            raise MappingConfigurationError(f"invalid unit_multiplier for {target}")
