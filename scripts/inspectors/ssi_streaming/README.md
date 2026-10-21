# inspectors/ssi_streaming — tool runbook

[Tiếng Việt](README.vi.md) · [CLI](../../../docs/CLI_USAGE.md)

Run from the root with the Python 3.11 venv and requirements installed. Stock dates accept DD/MM/YYYY or ISO; Phase 0 reconciliation requires ISO. Parser success is separate from data validity; examples were checked offline only. NOT_IMPLEMENTED scripts retain compatibility options but never call SSI/DB, even with --write; help exits 0, operational invocation returns FAILED/NOT_IMPLEMENTED JSON and exit 1.

## `scripts/inspectors/ssi_streaming/inspect.py`

Former negotiate/run inspector; every subcommand including list is disabled.

**NOT_IMPLEMENTED**. Dependency: None / không có. Output: FAILED + error_type NOT_IMPLEMENTED; exit 1.

```bash
python -m scripts.inspectors.ssi_streaming.inspect --help
python -m scripts.inspectors.ssi_streaming.inspect run --help
```

| Argument / alias | Parser rules (required/default/choices/nargs) |
| --- | --- |
| `--timeout` | type=int, default=30 |
| `kind` | choices=[*STREAM_TYPES.keys(), 'all'] |
| `--symbols` | nargs='+', default=['SSI'] |
| `--index-codes` | nargs='+', default=['VNINDEX'] |
| `--timeout` | type=int, default=30 |
| `--max-messages` | type=int, default=3 |
| `--limit` | type=int, default=None |
| `--full-json` | action='store_true' |
| `--raw-frames` | action='store_true' |
| `--channel` |  |
| `--negotiate-only` | action='store_true' |

## Disabled subcommands

`list`, `negotiate` and `run` all return NOT_IMPLEMENTED, including the local list operation. negotiate has timeout default 30. run retains registry kinds (or all), symbols default SSI, index-codes VNINDEX, timeout 30, max-messages 3, optional limit, and full-json/raw-frames/channel/negotiate-only. Historical payload names are not proof of a working v3 protocol. No SSI/Supabase credentials are required because no services are accessed. Re-enabling requires a separately verified v3 streaming adapter.

## BLOCKED: direct file execution

`python scripts/inspectors/ssi_streaming/inspect.py --help` currently raises ImportError before parsing because inspect.py shadows the standard inspect module, creating a STREAM_TYPES circular import. Use module invocation below for local help; operational calls still return NOT_IMPLEMENTED/exit 1 without SSI/DB access. Fix imports/path in a separate code task.

```bash
python -m scripts.inspectors.ssi_streaming.inspect --help
python -m scripts.inspectors.ssi_streaming.inspect run --help
```

The kind parser retains `securities-status`, `quote`, `trade`, `foreign-room`, `index`, `realtime-bar`, `all`; these compatibility values do not enable ingestion.
