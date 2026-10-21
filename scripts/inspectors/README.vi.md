# Inspector hiện tại

[English](README.md)

REST v3 chỉ đọc; streaming chưa triển khai, không kết nối SSI/DB.

- [REST v3](ssi_rest/README.vi.md)
- [Streaming NOT_IMPLEMENTED](ssi_streaming/README.vi.md)

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-daily --symbol SSI --date 19/10/2026 --show-mapping
python -m scripts.inspectors.ssi_streaming.inspect --help
```
