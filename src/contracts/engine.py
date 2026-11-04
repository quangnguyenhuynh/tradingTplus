"""Provider-neutral, side-effect-free record mapping engine."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .registry import get_contract, get_mapping
from .transforms import TRANSFORMS, TransformError
from decimal import Decimal
from .numeric import exact_binary

@dataclass(frozen=True)
class MappingResult:
    candidate: dict[str, Any] | None
    report: dict[str, Any]
    partial_candidate: dict[str, Any] | None = None

_MISSING = object()
def _same(left: Any, right: Any) -> bool:
    if isinstance(left, (int, Decimal)) and not isinstance(left, bool) and isinstance(right, (int, Decimal)) and not isinstance(right, bool):
        return left == right
    return type(left) is type(right) and left == right

def map_record(source_id: str, dataset: str, record: dict[str, Any], context: dict[str, Any] | None = None, *, mapping_version: str | None = None, contract_version: str | None = None) -> MappingResult:
    if not isinstance(record, dict): raise TypeError("source record must be a dictionary")
    context = dict(context or {})
    mapping = get_mapping(source_id, dataset, mapping_version)
    contract = get_contract(dataset, contract_version or mapping["contract_version"])
    lower: dict[str, list[tuple[str, Any]]] = {}
    for key, value in record.items(): lower.setdefault(str(key).casefold(), []).append((str(key), value))
    used: set[str] = set(); candidate: dict[str, Any] = {}; errors: list[dict[str, Any]] = []
    missing_required: list[str] = []; missing_optional: list[str] = []; conflicts: list[dict[str, Any]] = []
    for target, rule in mapping["fields"].items():
        if rule.get("derived"):
            # Derived values are populated by an explicit post-mapping layer.
            candidate[target] = None
            continue
        if rule.get("unsupported"):
            candidate[target] = None
            if contract["fields"][target]["required"]:
                missing_required.append(target)
            continue
        values: list[tuple[str, Any]] = []
        if rule.get("aliases"):
            for alias in rule["aliases"]: values.extend(lower.get(alias.casefold(), []))
            used.update(key for key, _ in values)
            values = [(key, value) for key, value in values if value is not None and value != ""]
            raw = values[0][1] if values else _MISSING
        elif "context" in rule:
            raw = context.get(rule["context"], _MISSING)
            if raw is None or raw == "": raw = _MISSING
        else: raw = rule["constant"]
        required = contract["fields"][target]["required"]
        if raw is _MISSING:
            (missing_required if required else missing_optional).append(target); candidate[target] = None; continue
        normalized = []
        for key, value in values or [("<context>", raw)]:
            try: normalized.append((key, TRANSFORMS[rule["transform"]](value, {**context, 'mapping_source_field': key})))
            except TransformError as exc: errors.append({"field": target, "source_field": key, "code": "TRANSFORM_ERROR", "message": str(exc)})
        if not normalized: candidate[target] = None; continue
        if any(not _same(normalized[0][1], item[1]) for item in normalized[1:]):
            conflict = {"field": target, "code": "ALIAS_CONFLICT", "source_fields": [item[0] for item in normalized]}; conflicts.append(conflict); errors.append(conflict); candidate[target] = None; continue
        value = normalized[0][1]
        if value is not None and "unit_multiplier" in rule:
            if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                value = exact_binary(value, rule['unit_multiplier'], 'multiply') if isinstance(value, Decimal) else value * rule['unit_multiplier']
            else: errors.append({"field": target, "code": "INVALID_UNIT_CONVERSION"})
        spec = contract["fields"][target]
        if value is None and not spec["nullable"]: errors.append({"field": target, "code": "NULL_NOT_ALLOWED"})
        if value is not None and spec.get("minimum") is not None and value < spec["minimum"]: errors.append({"field": target, "code": "BELOW_MINIMUM"})
        if value is not None and spec.get("allowed") and value not in spec["allowed"]: errors.append({"field": target, "code": "NOT_ALLOWED"})
        candidate[target] = value
    for field in missing_required: errors.append({"field": field, "code": "MISSING_REQUIRED"})
    report = {"source": source_id, "dataset": dataset, "contract_version": contract["contract_version"], "mapping_version": mapping["mapping_version"], "records_received": 1, "records_valid": 0 if errors else 1, "records_rejected": 1 if errors else 0, "missing_required": missing_required, "missing_optional": missing_optional, "unused_source_fields": [str(key) for key in record if str(key) not in used], "transform_errors": [e for e in errors if e["code"] == "TRANSFORM_ERROR"], "alias_conflicts": conflicts, "contract_errors": [e for e in errors if e["code"] not in {"TRANSFORM_ERROR", "ALIAS_CONFLICT"}], "errors": errors}
    unsupported = {field: rule["reason"] for field, rule in mapping["fields"].items() if rule.get("unsupported")}
    if source_id == 'ssi_v3' and dataset in ('stock_daily', 'index_daily'):
        report['predecoded_float_source_fields'] = [str(key) for key, value in record.items() if isinstance(value, float)]
        float_keys={key.casefold() for key in report['predecoded_float_source_fields']}
        report['predecoded_float_fields']=[field for field,rule in mapping['fields'].items()
            if rule.get('transform') in ('decimal','exact_int') and any(alias.casefold() in float_keys for alias in rule.get('aliases',[]))]
        report['precision_note'] = 'Predecoded float inputs cannot establish original source digits; HTTP daily and exact audit paths parse bytes/text with Decimal'
    if unsupported:
        report["unsupported_fields"] = unsupported
    derived = [field for field, rule in mapping["fields"].items() if rule.get("derived")]
    if derived:
        report["derived_fields"] = derived
    return MappingResult(None if errors else candidate, report, dict(candidate))
