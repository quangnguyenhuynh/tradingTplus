# Backfill dữ liệu nguồn production

## Mục đích và kiến trúc

Backfill chạy lại đúng hợp đồng EOD Phase 0 hiện có cho một khoảng lịch sử bao gồm cả hai đầu:

```text
mỗi ngày thường ứng viên
→ run_eod_pipeline(DD/MM/YYYY) đúng một lần
→ daily ingest
→ intraday 1m ingest
→ kiểm tra completeness ingest
→ OK / PARTIAL / FAILED
```

Backfill không chứa implementation riêng để fetch SSI, map, validate, persist, tính feature, signal hoặc backtest. Ngày thường chỉ là ứng viên theo lịch; response SSI rỗng vào ngày lễ hoặc ngày không giao dịch vẫn được phản ánh trong summary EOD, không tạo dòng giả hay thay dữ liệu thiếu bằng 0.

## CLI và ví dụ

Hai đầu mút đều bắt buộc và đều thuộc khoảng chạy:

```bash
python main.py backfill --from DD/MM/YYYY --to DD/MM/YYYY
python main.py backfill --from-date DD/MM/YYYY --to-date DD/MM/YYYY
```

Ví dụ:

```bash
python main.py backfill --from 10/07/2026 --to 14/07/2026
```

Ngày dùng định dạng ngày thị trường Việt Nam. Future date và khoảng đảo ngược bị từ chối. Pipeline đi tuần tự theo ngày lịch; thứ Bảy và Chủ nhật được bỏ qua và ghi trong `skipped_weekend_dates`. Khoảng chỉ có cuối tuần là no-op thành công với `processed_days=0`, `status=OK`.

## Dữ liệu bị ảnh hưởng và chạy lại

Khi chủ động chạy, command có thể ảnh hưởng đúng các bảng giống như chạy EOD tuần tự: `raw_daily`, `stock_daily`, `index_daily`, các bảng master index liên quan, `raw_intraday`, và `stock_intraday` với `timeframe='1m'`. Completeness validation đọc các bảng dữ liệu nguồn này. Ghi thực tế phụ thuộc response SSI và service EOD hiện có.

Các conflict key persistence hiện có giữ hợp đồng idempotency của EOD khi rerun; backfill không thêm cách persist khác. Hãy xác minh một ngày giao dịch lịch sử trước khi mở rộng khoảng. Không có production backfill nào tự chạy sau deploy.

Feature, signal và backtest **không tự động chạy**. Chỉ chạy pipeline downstream riêng sau khi đã xác minh dữ liệu nguồn và completeness.

## Hợp đồng summary và status

JSON summary cấp khoảng gồm `flow`, `from_date`, `to_date`, `requested_calendar_days`, `processed_days`, `skipped_weekend_days`, `skipped_weekend_dates`, `ok_days`, `partial_days`, `failed_days`, `error_count`, `errors`, `day_summaries`, và `status`. Summary EOD thành công được giữ nguyên. Exception được chặn tại biên ngày, ghi rõ ngày và message, rồi các ngày sau tiếp tục.

- `OK`: mọi ngày đã xử lý đều `OK` (bao gồm no-op không có ngày xử lý như đã mô tả).
- `FAILED`: mọi ngày đã xử lý đều `FAILED`.
- `PARTIAL`: status bị trộn, hoặc có ít nhất một ngày `PARTIAL`.

Exit code là `0` cho `OK` hoặc `PARTIAL`, `1` cho `FAILED` hoặc runtime failure chưa xử lý, và `2` cho CLI argument/khoảng ngày không hợp lệ.

## Compatibility và giới hạn

`src.pipeline.backfill.backfill(...)` được giữ làm wrapper deprecated. Hàm chấp nhận ngày ISO legacy để giữ compatibility import, chuyển định dạng rồi delegate sang `run_backfill_pipeline()`; symbol scope và future-date override bị từ chối vì EOD không hỗ trợ các hợp đồng đó. `scripts/backfill_sample.py` cũng deprecated và delegate sang pipeline production.

Backfill chỉ bỏ qua cuối tuần, không tự nhận biết ngày nghỉ sàn. Không có `--symbols`, chạy song song, retry ngoài retry hữu hạn của SSI/database client hiện có, tự tính feature, hoặc transaction bao trùm nhiều ngày. Failure cấp ngày có thể để lại partial write giống một EOD bị gián đoạn; cần đọc summary được giữ lại rồi rerun an toàn.

## Test

```bash
python -m pytest -q tests/pipeline/test_backfill_pipeline.py
python -m pytest -q tests/cli/test_cli_refactor.py
python -m pytest -q tests/pipeline/test_eod_pipeline.py
python -m pytest -q
```
