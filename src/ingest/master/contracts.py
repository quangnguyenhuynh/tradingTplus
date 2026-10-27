"""Canonical master schema/validation, independent of provider version."""
from __future__ import annotations

from datetime import date
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import json
import re
from collections import Counter

KEYS = {
    "symbols": ("symbol",), "securities": ("symbol",),
    "index_master": ("index_code",), "index_components": ("index_code", "symbol"),
}
NUMERIC = frozenset(("lot_size", "listed_share", *(
    f"tick_{kind}{n}" for n in range(1, 5) for kind in ("price", "increment")
)))
DATES = frozenset(("issue_date", "maturity_date", "first_trading_date", "last_trading_date"))
FIELDS = {
    "symbols": frozenset(("market", "name")),
    "securities": frozenset(("market", "stock_name", "stock_en_name", "sec_type",
                              "exchange", "issuer", "raw")) | NUMERIC | DATES,
    "index_master": frozenset(("index_name", "exchange", "raw")),
    "index_components": frozenset(("exchange", "raw")),
}
DEFAULTS = {"symbols": {"status": "inactive", "intraday_status": "inactive"},
            "index_master": {"status": "inactive"}}


def identity(dataset: str, row: dict) -> tuple[str, ...]:
    return tuple(row[k] for k in KEYS[dataset])


def canonical_record(dataset: str, row: dict) -> dict:
    """Missing optional values stay None; source cannot supply local controls."""
    if not isinstance(row, dict) or set(row) - (set(KEYS[dataset]) | FIELDS[dataset]):
        raise ValueError("Invalid canonical columns")
    result = deepcopy(row)
    for key in KEYS[dataset]:
        value = row.get(key)
        if not isinstance(value, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{0,63}", value.strip().upper()):
            raise ValueError("Invalid master identity")
        result[key] = value.strip().upper()
    for key, value in row.items():
        if key in KEYS[dataset] or value is None:
            continue
        if key in NUMERIC:
            try:
                number = Decimal(str(value))
            except (InvalidOperation, ValueError):
                raise ValueError("Invalid numeric master field") from None
            if isinstance(value, (bool, float)) or not number.is_finite() or number < 0:
                raise ValueError("Invalid numeric master field")
            result[key] = str(number)  # JSON-safe exact decimal, no float rounding.
        elif key in DATES:
            if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
                raise ValueError("Invalid master date")
        elif key == "raw":
            if not isinstance(value, dict):
                raise ValueError("Invalid master raw object")
            json.dumps(value, allow_nan=False)
        elif not isinstance(value, str) or not value.strip():
            raise ValueError("Invalid master text field")
    return result


def equivalent(key: str, left, right) -> bool:
    if key in NUMERIC and left is not None and right is not None:
        try:
            return Decimal(str(left)) == Decimal(str(right))
        except InvalidOperation:
            return False
    return left == right


def retention_check(dataset, records, existing, policy):
    """Detect unexplained group/universe drops before any missing classification."""
    if not policy:
        return {}
    field = policy.get('group_field')
    if field not in FIELDS[dataset]:
        raise ValueError('Invalid retention grouping field')
    fraction = Decimal(policy.get('minimum_fraction', '0'))
    if not fraction.is_finite() or not 0 < fraction <= 1:
        raise ValueError('Invalid retention threshold')
    current = Counter(row.get(field) for row in records)
    previous = Counter(row.get(field) for row in existing)
    # Include all rows in total guard even if a legacy market is NULL/noncanonical.
    reduced = len(records) < len(existing) * fraction
    groups = []
    for group, count in previous.items():
        if group is not None:
            bad = current[group] < count * fraction
            reduced |= bad
            groups.append({'group': group, 'existing_count': count,
                           'source_count': current[group], 'reduced': bad})
    result = {'status': 'BLOCKED' if reduced else 'PASS', 'group_field': field,
            'minimum_fraction': str(fraction), 'existing_count': len(existing),
            'source_count': len(records), 'groups': groups}
    distribution_field = policy.get('distribution_field')
    if distribution_field is not None:
        if distribution_field not in FIELDS[dataset]:
            raise ValueError('Invalid distribution field')
        old_types = Counter(row.get(distribution_field) for row in existing)
        new_types = Counter(row.get(distribution_field) for row in records)
        result['distribution_comparison'] = [
            {'value': kind, 'existing_count': old_types[kind], 'source_count': new_types[kind],
             'change': new_types[kind] - old_types[kind]}
            for kind in sorted(old_types.keys() | new_types.keys(), key=lambda value: str(value))]
    return result


def compare(dataset: str, records: list[dict], existing: list[dict]):
    """Plan an entire dataset before mutation; no deletes or NULL overwrites."""
    current = {}
    for row in existing:
        key = identity(dataset, row)
        # Case-sensitive DB keys must already match canonical identities.
        if key != identity(dataset, canonical_record(dataset, {k: row[k] for k in KEYS[dataset]})) or key in current:
            raise ValueError("Conflicting database master identity")
        current[key] = row
    seen, plan, classifications = set(), [], []
    for candidate in records:
        row = canonical_record(dataset, candidate)
        key = identity(dataset, row)
        if key in seen:
            raise ValueError("Duplicate canonical identity")
        seen.add(key)
        old = current.get(key)
        descriptive = {k: v for k, v in row.items() if k in FIELDS[dataset] and v is not None}
        if old is None:
            payload = {**row, **DEFAULTS.get(dataset, {})}
            classification = "NEW"
        else:
            payload = {k: v for k, v in descriptive.items() if not equivalent(k, old.get(k), v)}
            classification = "CHANGED" if payload else "UNCHANGED"
        classifications.append({"identity": dict(zip(KEYS[dataset], key)), "classification": classification,
                                "fields": sorted(payload) if classification == "CHANGED" else []})
        if classification != "UNCHANGED":
            plan.append({"identity": dict(zip(KEYS[dataset], key)), "classification": classification,
                         "payload": payload, "before": deepcopy(old)})
    classifications.extend({"identity": dict(zip(KEYS[dataset], key)), "classification": "SOURCE_MISSING", "fields": []}
                           for key in current if key not in seen)
    return plan, classifications
