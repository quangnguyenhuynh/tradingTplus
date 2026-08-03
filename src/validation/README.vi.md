# Validation dữ liệu

Model và rule validation cho record daily, intraday và streaming.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## File

- `models.py`: cấu trúc result/status validation.
- `daily_validator.py`: field bắt buộc, ngày, OHLC, giá trần/sàn, volume/value và consistency daily.
- `intraday_validator.py`: kiểm tra từng candle và batch intraday.
- `streaming_validator.py`: kiểm tra payload streaming và row đã map.
- `logging_utils.py`: helper log validation nhất quán.
- `phase0.py`: kiểm tra schema, lineage payload và đối chiếu raw/clean/feature có giới hạn, chỉ đọc.
- `__init__.py`: export package.

## Nguyên tắc

- Validate trước khi ghi clean data khi hợp đồng pipeline yêu cầu.
- Giữ bằng chứng raw và báo giá trị nguồn đáng ngờ thay vì tự sửa âm thầm.
- Loại hoặc quarantine timestamp sai; không thay bằng thời gian hiện tại.
- Giữ `NULL` cho field chưa biết nếu chưa có quy tắc đã kiểm chứng.
- Giá tham chiếu, trần và sàn daily là context tùy chọn. Chỉ chạy kiểm tra phụ thuộc khi có đủ input. Dải OHLC đồng nhất và nằm hoàn toàn cùng một phía ngoài limits được giữ dưới dạng corporate-action warning; vi phạm limit đơn lẻ và OHLC sai vẫn là lỗi blocking.
- Kiểm tra quan hệ OHLC, số hữu hạn, volume/value không âm, symbol/date, duplicate, session và batch consistency khi phù hợp.
- Completeness phụ thuộc symbol, trading date, source, timeframe và session; một số candle cố định không đủ làm chuẩn.
- Check Phase 0 phân loại evidence live bị thiếu là `UNKNOWN`; payload intraday lịch sử NULL là bình thường và validation không bao giờ backfill.

## Test

```bash
python -m pytest -q tests/validation
```

Mỗi rule mới cần test tập trung cho case đúng, sai, thiếu và boundary.
