# Module rule signal

Các class rule dùng lại cho tầng signal research/MVP hiện tại.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## File

- `base.py`: interface rule chung và hợp đồng dùng chung.
- `trend.py`: rule theo xu hướng.
- `breakout.py`: rule breakout.
- `reversal.py`: rule đảo chiều.
- `__init__.py`: export package.

## Ranh giới

- Rule đọc feature đã được kiểm chứng; không gọi SSI hoặc ghi raw/clean table.
- Mỗi signal match phải giải thích được và có symbol, timeframe, time, type/score và reason theo hợp đồng lưu của caller.
- Không âm thầm gộp các match mâu thuẫn.
- Threshold chưa được xem là tối ưu hoặc production-validated trong Phase 0.
- Không dùng vài indicator 1 phút làm cơ sở chính cho luận điểm T+3/T+5.

Chỉ thêm hoặc sửa rule trong task signal rõ ràng sau khi feature contract và dữ liệu lịch sử đã được kiểm chứng.
