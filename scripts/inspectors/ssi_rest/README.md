# scripts/inspectors/ssi_rest

Read-only native/canonical SSI v3 inspection with exact raw payload, mapping reports and normalized previews. No v2 authentication or endpoints.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `client.py`
- `datasets.py`
- `endpoints.py`
- `inspect.py`
- `mapping.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-daily --symbol SSI --date 2026-10-19 --data-source ssi_v3
python scripts/inspectors/ssi_rest/inspect.py run index-daily --index-code VNINDEX --date 2026-10-19 --show-mapping
```

`--full-json` preserves full response display, `--limit` bounds display only, and supported `--page-index`/`--page-size` control requests. Dates accept YYYY-MM-DD or DD/MM/YYYY. Preview capabilities remain read-only and do not imply production adapter readiness. SSI v2 selection fails before constructing a session.
