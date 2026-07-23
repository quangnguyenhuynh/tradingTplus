# Backfill production

[English](README.md) | [Tiếng Việt](README.vi.md)

## Mục đích

Lệnh backfill production chạy lại đúng luồng EOD ingest và kiểm tra completeness hiện có cho một khoảng ngày lịch sử bao gồm cả ngày đầu và ngày cuối.

Với mỗi ngày trong tuần, backfill gọi `src.pipeline.eod.run_eod_pipeline()`:

```text
daily ingest
→ intraday ingest 1m
→ kiểm tra ingest completeness
→ OK / PARTIAL / FAILED
```

Backfill chỉ là tầng orchestration. Nó không viết lại hoặc nhân đôi logic fetch, mapping, validation hay persistence của daily và intraday.

## CLI

```bash
python main.py backfill --from DD/MM/YYYY --to DD/MM/YYYY
```

Có thể dùng alias `--from-date` và `--to-date`.

Ví dụ:

```bash
python main.py backfill --from 01/07/2026 --to 10/07/2026
```

Nên bắt đầu với khoảng ngày nhỏ và kiểm tra JSON summary trước khi chạy khoảng dài hơn.

## Phạm vi và an toàn

- Hai ngày đầu/cuối đều được xử lý.
- CLI production dùng định dạng `DD/MM/YYYY`.
- Không cho chạy ngày tương lai.
- `--from` phải nhỏ hơn hoặc bằng `--to`.
- Thứ Bảy và Chủ nhật được bỏ qua và liệt kê trong summary.
- Khoảng ngày không có ngày trong tuần sẽ bị từ chối.
- Ngày trong tuần chỉ là ứng viên theo lịch, không phải bằng chứng đó là ngày giao dịch. Lệnh không tạo dữ liệu giả cho ngày lễ hoặc SSI trả rỗng; kết quả EOD của từng ngày phản ánh đúng dữ liệu thực tế.
- Lệnh xử lý cùng toàn bộ danh sách mã active như EOD hiện tại. Không mở `--symbols` vì EOD hiện chưa hỗ trợ scope theo symbol.
- Các ngày chạy tuần tự để phạm vi ghi dữ liệu và summary dễ theo dõi.

## Dữ liệu đọc và ghi

Mỗi ngày được xử lý có tác động dữ liệu giống lệnh:

```bash
python main.py eod DD/MM/YYYY
```

Bao gồm các luồng daily, intraday 1m, index, raw/clean persistence và completeness mà EOD cùng các pipeline con hiện đang quản lý.

Backfill không tự tính feature, không sinh signal và không chạy backtest.

## Summary trả về

Lệnh in một JSON object gồm:

- `from_date`, `to_date`
- `requested_calendar_days`
- `processed_days`
- `skipped_weekend_days`, `skipped_weekend_dates`
- `ok_days`, `partial_days`, `failed_days`
- `errors`
- `day_summaries`, giữ nguyên EOD summary của từng ngày được xử lý
- `status` cuối cùng

Quy tắc status cuối:

- `OK`: tất cả ngày được xử lý đều `OK`.
- `FAILED`: tất cả ngày được xử lý đều `FAILED`.
- `PARTIAL`: kết quả trộn lẫn, hoặc có ít nhất một ngày `PARTIAL`.

Exit code theo contract CLI chính:

- `0`: `OK` hoặc `PARTIAL`; vẫn phải đọc JSON summary.
- `1`: status cuối là `FAILED` hoặc có runtime error chưa xử lý.
- `2`: tham số CLI hoặc khoảng ngày không hợp lệ.

## Chạy lại

Lệnh dùng lại persistence method và conflict key hiện có. Vì vậy chạy lại một khoảng ngày rõ ràng nhằm cập nhật/đối chiếu cùng các raw và clean record, không tạo side effect cho feature, signal hoặc backtest.

Trước khi chạy production, cần xác nhận database đang deploy có đủ unique index tương ứng với các `on_conflict` hiện tại của repo.

## Wrapper cũ

`scripts/backfill_sample.py` chỉ còn là compatibility wrapper và gọi cùng pipeline production. Nên dùng CLI trong `main.py`.

## Test

```bash
python -m pytest -q tests/pipeline/test_backfill_pipeline.py
python -m pytest -q tests/cli/test_cli_refactor.py
python -m pytest -q tests/pipeline/test_eod_pipeline.py
python -m pytest -q
```

Smoke test SSI/Supabase phải có scope rõ ràng và mặc định read-only, trừ khi chủ động yêu cầu ghi production.

## Giới hạn hiện tại

- Không tự suy luận hoặc tạo lịch nghỉ lễ của sở giao dịch.
- Chưa có mode theo symbol khi EOD vẫn chạy toàn thị trường.
- Không tự retry riêng các ngày fail sau khi cả khoảng kết thúc; cần rerun một khoảng nhỏ rõ ràng.
- Không tự backfill feature. Chỉ chạy `python main.py features ...` riêng sau khi dữ liệu nguồn đã được kiểm chứng.
