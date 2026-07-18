# Test validation

Các test tập trung cho package validation.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## File

- `test_daily_validator.py`: field bắt buộc daily, OHLC, trần/sàn, volume/value và ngày.
- `test_intraday_validator.py`: validation candle và batch intraday.
- `test_streaming_validator.py`: validation payload/mapping streaming.

## Command

```bash
python -m pytest -q tests/validation
```

## Thiết kế test

- Bao phủ case đúng, sai, thiếu, malformed và boundary.
- Test deterministic, không phụ thuộc SSI/Supabase live.
- Assert cả validation status và chi tiết issue, không chỉ boolean.
- Mỗi bug data-quality production cần regression test.
- Không làm yếu rule chỉ để chấp nhận anomaly nguồn chưa giải thích; trước tiên phải giữ và ghi nhận bằng chứng.
