# Canonical data contracts and source mappings

This package separates the application's clean-data meaning from a provider's payload shape. `definitions.json` is the canonical dictionary for `stock_daily`, 1-minute `stock_intraday`, and `index_daily`. Each field states its business meaning, type, unit, required/null policy, field constraints, and relevant date/time/timeframe convention. Every dataset currently has `contract_version: 1.0.0`.

`mappings/ssi_v2.json` is the independently versioned (`mapping_version: 1.0.0`) SSI v2 adapter. It declares only confirmed aliases, allow-listed transforms, source-specific missing/placeholder handling, and any evidenced unit multiplier. In particular, SSI v2 zero placeholders for daily reference/ceiling/floor prices use `ssi_v2_zero_price_to_null`; this is not a global contract rule.

## Processing and reports

`map_record(source_id, dataset, record, context)` validates registry compatibility, reads declared top-level fields only, normalizes values, validates field constraints, and returns a `MappingResult`. It never searches recursively, guesses names, calls an API/database, writes files, or computes downstream features. Unknown sources/datasets/versions fail without fallback.

The report identifies source/dataset/versions and record counts, then separates required and optional missing fields, unused source fields, conversion failures, alias conflicts, and contract violations. Counts are record-level; field lists can contain multiple findings for one rejected record. The ingest services expose reports under the separate `mapping_report` metadata key and do not send report keys to clean tables. Existing business validators still run after mapping.

Offline example:

```python
from src.data_contracts import map_record

result = map_record(
    "ssi_v2", "stock_daily",
    {"Symbol": "SSI", "TradingDate": "18/06/2026", "ClosePrice": "25.5"},
    {"symbol": "SSI", "date": "18/06/2026"},
)
print(result.candidate)
print(result.report)
```

## Registering another mapping

1. Confirm the provider's API and payload semantics independently; mapping does not implement authentication, requests, or pagination.
2. Reuse a canonical dataset only when its meanings and units match. Change the dictionary/version deliberately if the application contract itself changes.
3. Add a source JSON file with an exact `source_id`, dataset, compatible `contract_version`, new `mapping_version`, and one rule per supported target.
4. Declare exact aliases and an allow-listed named transform. Use `context` only for explicit request context and `constant` only for fixed contract values such as `1m`. Declare `unit_multiplier` only with source evidence.
5. Add a pure transform to `TRANSFORMS` when simple conversion is insufficient; arbitrary expressions and `eval`/`exec` are forbidden.
6. Validate with `get_mapping(...)` and an offline fixture, including missing, malformed, duplicate-alias, and unused-field cases.

Mapping does not prove that a source supplies every data group and does not replace its connector. Only SSI v2 is registered in this phase; no SSI v3 support is implied.
