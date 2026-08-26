# Script manual, smoke và maintenance

Thư mục `scripts/` chứa các tool vận hành chạy tường minh. Đây không phải entrypoint production chính; production flow nên chạy qua `main.py`.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)
- REST inspector: [ssi_api_inspector/README.vi.md](ssi_api_inspector/README.vi.md)
- Streaming inspector: [ssi_streaming_inspector/README.vi.md](ssi_streaming_inspector/README.vi.md)

## Nhãn an toàn

| Nhãn | Ý nghĩa |
| --- | --- |
| `READ-ONLY` | Chỉ đọc API/database, không ghi dữ liệu. |
| `DRY-RUN DEFAULT` | Chỉ ghi khi truyền `--write` rõ ràng. |
| `WRITES DB` | Có ghi database; phải rà soát phạm vi trước khi chạy. |

## Script chính

| Script | Mức độ | Mục đích |
| --- | --- | --- |
| `check_supabase.py` | `READ-ONLY` | Kiểm tra cấu hình Supabase và khả năng đọc bảng core. |
| `check_ssi_ingest_schema.py` | `READ-ONLY` | Kiểm tra bảng/cột cần thiết cho SSI ingest. |
| `check_complete_ssi_ingest.py` | `DRY-RUN DEFAULT` | Kiểm tra payload SSI và mapping raw/clean theo symbol/date có phạm vi. |
| `check_ingest.py` | `READ-ONLY` | Báo completeness ingest theo ngày. |
| `phase0_validate_schema.py` | `READ-ONLY` | Kiểm tra contract catalog payload/RPC/index qua kết nối PostgreSQL bị ép read-only. |
| `phase0_reconcile_sample.py` | `READ-ONLY` | Kiểm tra lineage payload có giới hạn và một sample raw/clean/feature explicit với kết quả PASS/FAIL/UNKNOWN. |
| `eod_dry_run.py` | `READ-ONLY` | Kiểm tra trạng thái EOD không ghi database. |
| `fetch_one_day.py` | `DRY-RUN DEFAULT` | Kiểm tra hoặc ghi đúng một mã/một ngày. |
| `backfill_sample.py` | `WRITES DB` | Delegate deprecated sang backfill production kết hợp; bắt buộc khoảng ngày bao gồm hai đầu. |
| `run_features.py` | `WRITES DB` | Chạy feature pipeline riêng. |
| `snapshot_stream.py` | `DRY-RUN DEFAULT` | Thu snapshot streaming có giới hạn. |
| `snapshot_orderbook.py` | `DRY-RUN DEFAULT` | Thu quote/orderbook snapshot từ streaming payload được hỗ trợ. |

## Thứ tự khuyến nghị

```text
1. check_supabase.py
2. check_ssi_ingest_schema.py
3. dùng SSI inspector khi cần xem raw payload
4. check_complete_ssi_ingest.py ở chế độ read-only
5. fetch_one_day.py --dry-run
6. chạy ingest/write có phạm vi
7. check_ingest.py hoặc eod_dry_run.py
8. chạy feature riêng sau khi raw/clean/completeness đã được kiểm chứng
```

## Quy tắc

- Không nối ingest → feature → signal → backtest trong một script tiện lợi.
- Script ghi dữ liệu phải bắt buộc phạm vi symbol/date rõ ràng.
- Không in secret, token hoặc nội dung `.env`.
- Không tạo dòng giả cho cuối tuần, ngày nghỉ, response rỗng hoặc endpoint không hỗ trợ.
- `stock_intraday` chỉ lưu `1m`; timeframe feature cao hơn được aggregate về sau.
- Không đánh giá khả năng sinh lợi khi dữ liệu Phase 0 chưa được kiểm chứng.

Chạy command từ root repo và đọc `--help` trước mọi tool có khả năng ghi.

Check đóng Phase 0 bắt buộc scope explicit và không tự suy diễn evidence live.
Dùng `PHASE0_DATABASE_URL=... python scripts/phase0_validate_schema.py` cho
metadata catalog và `python scripts/phase0_reconcile_sample.py --symbol SSI
--date YYYY-MM-DD --timeframe 1d` để reconcile. Có thể truyền exact
`--timestamp` cho `15m`/`60m`. Payload intraday lịch sử NULL là bình thường;
không có sample khác NULL sẽ trả `UNKNOWN`, không phải PASS.

Dùng `python main.py backfill-daily`, `backfill-intraday`, hoặc `backfill` kết hợp với khoảng ngày explicit cho production. Sample deprecated nhận `--symbols` tùy chọn nhưng không có future override, delegate sang cùng pipeline, bỏ qua cuối tuần và không tự chạy feature, signal hay backtest. Xem [`docs/backfill/README.vi.md`](../docs/backfill/README.vi.md).

> Cập nhật feature (issue #99): implementation thuộc `src/features/`. Dùng `features-daily` và `features-intraday` tách theo nguồn; `stock_features` và `intraday` là route tương thích. Intraday chỉ ghi bucket đã đóng, dùng open daily chính thức, indicator/high-low liên tục, baseline volume/value bucket tương ứng 20 ngày quan sát trước và flag nullable. Xem `src/features/README.vi.md`.
