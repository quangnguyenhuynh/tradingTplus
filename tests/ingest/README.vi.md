# Test ingest

Test việc chuẩn hóa dữ liệu SSI daily/intraday và điều phối ingest.

## File

- `test_fetch_one_day.py`: mapper/service daily và intraday, đổi UTC, field nullable, estimated value, timestamp sai, compatibility import và tách daily/intraday.
- `test_intraday_value.py`: tính intraday value ước tính và giữ NULL.
- `test_daily_ingest_payload_reuse.py`: tái sử dụng một payload `DailyStockPrice` cho raw, clean và foreign.
- `test_intraday_ingest_pipeline.py`: phạm vi symbol, daily context và trạng thái partial.
- `test_ingest_check.py`: khoảng ngày và số lượng trong truy vấn completeness.

```bash
python -m pytest -q tests/ingest
```
