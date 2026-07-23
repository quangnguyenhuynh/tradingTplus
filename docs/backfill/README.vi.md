# Backfill dữ liệu nguồn production

## Kiến trúc

TradingTPlus cung cấp ba pipeline khoảng ngày độc lập cho Phase 0:

```text
run_daily_backfill_pipeline()    -> daily ingest cho mọi ngày hợp lệ
run_intraday_backfill_pipeline() -> intraday 1m ingest cho mọi ngày hợp lệ
run_backfill_pipeline()          -> chạy xong nhánh daily -> chạy xong nhánh intraday
                                  -> kiểm tra completeness từng ngày hợp lệ
```

Không pipeline nào chạy feature, signal hoặc backtest. Pipeline không đoán ngày lễ trong tuần: response SSI rỗng và dữ liệu thiếu vẫn quan sát được, không tạo dòng giả hay âm thầm thay bằng 0.

## Command

```bash
python main.py backfill-daily --from 01/07/2026 --to 10/07/2026 --symbols SSI HPG
python main.py backfill-intraday --from 01/07/2026 --to 10/07/2026 --symbols SSI HPG
python main.py backfill --from 01/07/2026 --to 10/07/2026 --symbols SSI HPG
```

`--from-date` và `--to-date` là alias. Khoảng dùng `DD/MM/YYYY`, gồm cả hai đầu, từ chối ngày tương lai/khoảng đảo ngược, xử lý tuần tự, bỏ qua và báo cáo thứ Bảy/Chủ nhật. Khoảng chỉ có cuối tuần là no-op `OK`.

Symbol explicit được strip, đổi chữ hoa và loại trùng theo thứ tự đầu tiên đúng một lần trước khi xử lý; scope explicit rỗng không hợp lệ. Bỏ scope thì dùng symbol master hiện tại.

## Hành vi nhánh và ảnh hưởng dữ liệu

- **`backfill-daily`** chỉ chạy daily ingest lịch sử. Ingest index daily được giữ nguyên nhưng không đồng bộ index master theo từng ngày, nên lần chạy chủ động chỉ có thể ghi `raw_daily`, `stock_daily` và `index_daily`. `--symbols` chỉ giới hạn cổ phiếu. Command không chạy intraday hay completeness.
- **`backfill-intraday`** chỉ chạy ingest SSI intraday 1m lịch sử và có thể ghi `raw_intraday`, `stock_intraday` chỉ với `timeframe='1m'`. Pipeline đọc context `stock_daily` hiện có nếu có; thiếu context vẫn thể hiện bằng `PARTIAL`. Pipeline không tự chạy daily hay completeness.
- **`backfill`** chạy xong toàn bộ nhánh daily trước nhánh intraday, sau đó đọc bảng nguồn để kiểm tra completeness có scope cho từng ngày hợp lệ. Summary giữ cả hai nhánh và tạo summary `backfill-day` theo status tương thích EOD. Pipeline không gọi EOD trực tiếp.

Mỗi nhánh ghi exception theo ngày và tiếp tục ngày sau. Exception completeness cũng được ghi mà không làm mất kết quả hai nhánh. Status khoảng là `OK` khi mọi ngày xử lý đều `OK`, `FAILED` khi mọi ngày thất bại, và `PARTIAL` khi status trộn hoặc có ngày partial. Exit code là `0` cho `OK`/`PARTIAL`, `1` cho `FAILED`/runtime failure, và `2` cho argument sai.

Không có backfill production tự chạy sau deploy, và chỉ deploy code không yêu cầu chạy lại lịch sử. Chỉ chạy phạm vi ngày/symbol sửa chữa đã được cho phép rõ ràng.

## Compatibility

`backfill(...)` vẫn deprecated, nhận ngày ISO legacy, từ chối `allow_future=True`, và delegate sang `run_backfill_pipeline()`. `scripts/backfill_sample.py` vẫn là delegate deprecated sang command kết hợp.

## Test

```bash
python -m pytest -q tests/pipeline/test_backfill_pipeline.py
python -m pytest -q tests/cli/test_cli_refactor.py
python -m pytest -q tests/pipeline/test_eod_pipeline.py
python -m pytest -q
```
