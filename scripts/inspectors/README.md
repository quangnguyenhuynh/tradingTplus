# Current inspectors

[Tiếng Việt](README.vi.md)

REST v3 is read-only; streaming is not implemented and never connects to SSI/DB.

- [REST v3](ssi_rest/README.md)
- [Streaming NOT_IMPLEMENTED](ssi_streaming/README.md)

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-daily --symbol SSI --date 19/10/2026 --show-mapping
python -m scripts.inspectors.ssi_streaming.inspect --help
```
