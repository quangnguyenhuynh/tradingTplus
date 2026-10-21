# src/diagnostics

[English](README.md)

## Công cụ chất lượng và completeness

Các check active dưới đây đều READ-ONLY — database read. `check_ingest.py` kiểm tra coverage stock daily/intraday đã lưu; sau khi hàm chạy xong và in kết quả, script luôn trả 0 nên phải đọc trạng thái completeness trong JSON. Vẫn báo thiếu intraday dù ingest đang tắt. `check_supabase.py` không có tham số CLI/help parser: kiểm tra kết nối bảng lõi, không chứng nhận toàn bộ schema. `check_ssi_ingest_schema.py` select danh sách cột và in SQL kiểm tra index; kỳ vọng cột cũ có thể lệch contract 2.0, cần sửa code riêng, không đổi schema chỉ để chiều diagnostic.

`phase0_validate_schema.py` query catalog PostgreSQL chỉ đọc; ưu tiên biến môi trường thay vì ghi URL DB vào shell history. `phase0_reconcile_sample.py` kiểm tra một mã/ngày/timeframe, tùy chọn timestamp chính xác và tolerance 1e-6. PASS/FAIL/UNKNOWN có ý nghĩa riêng với việc tiến trình chạy được. Xem [công cụ kiểm tra](../../scripts/checks/README.vi.md).

```bash
python scripts/checks/check_ingest.py --date 19/10/2026 --symbols SSI
python scripts/checks/check_supabase.py
python scripts/checks/check_ssi_ingest_schema.py
python scripts/checks/phase0_validate_schema.py
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-19 --timeframe 1d
```
## Script chẩn đoán, bảo trì và debug

[Danh mục script](../../scripts/README.vi.md) liệt kê mọi công cụ thực thi theo đường dẫn hiện tại. **`scripts/previews/run_features.py` là WRITE — feature calculation** dù nằm trong previews. Nó gọi engine, không có cờ dry-run/ngày và có thể xử lý lịch sử theo mode/watermark. Ưu tiên route feature main.py có ngày đích tường minh. Tên/vị trí script là vấn đề code riêng; task này không di chuyển.

`eod_dry_run.py`, `fetch_one_day.py`, capture, streaming inspector và complete SSI smoke check là stub đang tắt, không phải pipeline debug chạy được. SQL intraday-value cũ là artifact WRITE rộng không giới hạn mã/ngày, không phải CLI vận hành thường lệ; không dán vào production. Cần review riêng một sửa chữa có phạm vi.

```bash
python scripts/previews/run_features.py --mode incremental --symbols SSI --timeframes 1d
```

[CLI](../../docs/CLI_USAGE.vi.md)
