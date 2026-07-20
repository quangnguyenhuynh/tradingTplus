# Test legacy và research

Test cho code còn giữ để tương thích hoặc nghiên cứu nhưng chưa phải hành vi T+ production đã kiểm chứng.

`test_backtest_engine.py` kiểm tra MVP đang giữ lệnh theo số bar. Nó không chứng minh backtest T+3/T+5 theo phiên giao dịch là đúng và không được xem là bằng chứng sinh lợi.

```bash
python -m pytest -q tests/legacy
```
