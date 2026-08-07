# Mã nguồn ứng dụng

Python package chứa tích hợp SSI, persistence, validation, pipeline và feature deterministic.

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
| [`features/`](features/README.vi.md) | Tính và chạy feature daily/intraday tách theo nguồn. |
| [`engine/`](engine/README.vi.md) | Utility data-quality manual legacy. |
| [`strategies/`](strategies/README.vi.md) | Implementation research fixed-rule đang đóng băng. |
| [`signals/`](signals/README.vi.md) | Daily-setup/intraday-scan research đang đóng băng. |
| [`backtest/`](backtest/README.vi.md) | Replay/outcome fixed-rule research đang đóng băng. |
| [`utils/`](utils/README.vi.md) | Helper dùng chung cho thời gian thị trường Việt Nam có timezone. |

## Chiều phụ thuộc

```text
SSI clients → pipelines → validation/database
clean database data → feature pipeline chạy explicit
```

Ingest không được tự động gọi feature. Feature không tự gọi tầng research
downstream. Code strategy/signal/backtest fixed-rule vẫn tồn tại nhưng đang đóng
băng và đã bị thay thế bởi
[thiết kế historical analog cùng mã](../docs/phase1/HISTORICAL_ANALOG_SPEC.vi.md),
hiện chưa được triển khai.

## Hợp đồng dữ liệu

- `stock_daily` cung cấp feature `1d`.
- `stock_intraday` chỉ lưu nến clean `1m`.
- Timeframe intraday cao hơn được aggregate trong feature engine.
- Intraday `value` hiện ước tính bằng `round(close * volume)` và giữ `NULL` khi input thiếu/sai.
- Không tạo dữ liệu SSI giả hoặc âm thầm đổi missing thành 0.

## Phát triển

Chỉ sửa đúng phạm vi, giữ public function và schema contract, xử lý lỗi API/database rõ ràng và tạo migration khi đổi schema. Chạy test nhỏ liên quan trước rồi `python -m pytest -q` khi phù hợp.
