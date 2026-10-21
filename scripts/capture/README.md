# capture — tool runbook

[Tiếng Việt](README.vi.md) · [CLI](../../docs/CLI_USAGE.md)

Run from the root with the Python 3.11 venv and requirements installed. Stock dates accept DD/MM/YYYY or ISO; Phase 0 reconciliation requires ISO. Parser success is separate from data validity; examples were checked offline only. NOT_IMPLEMENTED scripts retain compatibility options but never call SSI/DB, even with --write; help exits 0, operational invocation returns FAILED/NOT_IMPLEMENTED JSON and exit 1.

## `scripts/capture/snapshot_stream.py`

Former bounded stream capture; disabled pending verified v3 protocol.

**NOT_IMPLEMENTED**. Dependency: None / không có. Output: FAILED + error_type NOT_IMPLEMENTED; exit 1.

```bash
python scripts/capture/snapshot_stream.py --help
```

| Argument / alias | Parser rules (required/default/choices/nargs) |
| --- | --- |
| `--symbols` | nargs='*', default=None |
| `--indexes` | nargs='*', default=['VNINDEX', 'VN30'] |
| `--timeout` | type=int, default=60 |
| `--limit` | type=int, default=20 |
| `--debug` | action='store_true' |
| `--write` | action='store_true', default=False |

## `scripts/capture/snapshot_orderbook.py`

Former depth snapshot capture; disabled pending verified v3 streaming.

**NOT_IMPLEMENTED**. Dependency: None / không có. Output: FAILED + error_type NOT_IMPLEMENTED; exit 1.

```bash
python scripts/capture/snapshot_orderbook.py --help
```

| Argument / alias | Parser rules (required/default/choices/nargs) |
| --- | --- |
| `symbols` | nargs='*' |
| `--timeout` | type=int, default=None |
| `--debug` | action='store_true' |
| `--write` | action='store_true', default=False |
| `--no-write` | action='store_true' |

## Future restoration

snapshot_stream retains symbols, indexes default VNINDEX VN30, timeout 60, limit 20 and debug/write. snapshot_orderbook uses positional symbols, optional timeout, debug and mutually exclusive --write/--no-write. Neither connects to v3 streaming or writes stream_* / stock_orderbook_snapshot. Old help is not production support; restoration needs verified protocol/auth/timestamp/session adapters. Do not infer a public REST depth endpoint. Historical snapshot data remains untouched.
