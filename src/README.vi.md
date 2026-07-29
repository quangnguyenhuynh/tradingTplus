# Mã nguồn ứng dụng

Python package chứa tích hợp SSI, persistence, validation, pipeline và các engine research.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Cấu trúc package

| Đường dẫn | Trách nhiệm |
| --- | --- |
| `config.py` | Cấu hình ứng dụng từ biến môi trường. |
| `intraday_value.py` | Hàm dùng chung tính intraday value ước tính. |
| [`ssi/`](ssi/README.vi.md) | Truy cập SSI REST và streaming. |
| [`database/`](database/README.vi.md) | Đọc/ghi Supabase. |
| [`validation/`](validation/README.vi.md) | Validation record raw/clean. |
| [`pipeline/`](pipeline/README.vi.md) | Orchestration production và các luồng ingest. |
| [`engine/`](engine/README.vi.md) | Tính feature và engine research downstream. |

## Chiều phụ thuộc

```text
SSI clients → pipelines → validation/database
clean database data → feature engine → signal/backtest research khi chạy riêng
```

Ingest không được tự động gọi feature, signal hoặc backtest. Code research downstream không được sửa hoặc ghi đè dữ liệu nguồn.

## Hợp đồng dữ liệu

- `stock_daily` cung cấp feature `1d`.
- `stock_intraday` chỉ lưu nến clean `1m`.
- Timeframe intraday cao hơn được aggregate trong feature engine.
- Intraday `value` hiện ước tính bằng `round(close * volume)` và giữ `NULL` khi input thiếu/sai.
- Không tạo dữ liệu SSI giả hoặc âm thầm đổi missing thành 0.

## Phát triển

Chỉ sửa đúng phạm vi, giữ public function và schema contract, xử lý lỗi API/database rõ ràng và tạo migration khi đổi schema. Chạy test nhỏ liên quan trước rồi `python -m pytest -q` khi phù hợp.

> Cập nhật feature (issue #99): implementation thuộc `src/features/`. Dùng `features-daily` và `features-intraday` tách theo nguồn; `features` và `intraday` là route tương thích. Intraday chỉ ghi bucket đã đóng, dùng open daily chính thức, indicator/high-low liên tục, baseline volume/value bucket tương ứng 20 ngày quan sát trước và flag nullable. Xem `src/features/README.vi.md`.
