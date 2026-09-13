# Test inspector

Contract test offline cho SSI REST inspector và streaming inspector chỉ đọc.

Phạm vi gồm đủ năm dataset REST chuẩn (mapping danh mục, identity trùng và validation trước network), registry endpoint/channel, dựng request, giải mã SignalR, che secret, reauthentication có giới hạn, status/exit code và đảm bảo không ghi database.

```bash
python -m pytest -q tests/inspectors
```
