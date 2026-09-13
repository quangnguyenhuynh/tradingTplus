# Inspector tests

Offline contract tests for the read-only SSI REST and streaming inspectors.

They cover all five canonical REST datasets (including catalog mapping, duplicate identities and pre-network validation), endpoint/channel registries, request construction, SignalR decoding, redaction, bounded reauthentication, status/exit-code behavior, and the absence of database writes.

```bash
python -m pytest -q tests/inspectors
```
