# Báo cáo kiểm chứng Phase 0

**Quyết định: COMPLETE_WITH_NOTES**
**Ngày đóng:** 03/08/2026
**Phạm vi:** hạ tầng dữ liệu, validation dữ liệu và kiểm chứng feature deterministic; chưa triển khai Phase 1.

## Gate đóng Phase 0

| Gate | Kết quả | Evidence |
| --- | --- | --- |
| Schema production | `PASS_WITH_MANUAL_APPLY_NOTE` | `20260802_atomic_replace_features.sql` và `20260803_add_raw_intraday_payload.sql` đã được apply thủ công bằng Supabase SQL Editor. Kiểm tra production chỉ đọc xác nhận `stock_raw_intraday.payload jsonb` nullable/không default, RPC atomic có `SECURITY DEFINER`, `search_path` rỗng an toàn, đúng quyền role và unique index feature bắt buộc. Supabase CLI migration history có thể không có record; Phase 0 chấp nhận vì schema deployed đúng. Không rerun/repair migration chỉ để sửa history. |
| Lineage payload intraday mới | `PASS` | Chủ dự án đã kiểm tra row ingest intraday mới có `stock_raw_intraday.payload` khác NULL. Payload lịch sử NULL là đúng thiết kế và không cần backfill. |
| Sample SSI → raw → clean → feature | `PASS` | Chủ dự án chọn symbol/ngày/timeframe daily và intraday trên production, đối chiếu source, raw, clean và feature. Field khớp gồm identity/mapping payload cùng OHLCV/value; không còn mismatch critical chưa giải thích. Report chưa lưu exact identifier của sample, nên run sau phải lưu command output và scope. |
| Regression offline | `PASS` | Test deterministic cover pagination, mapping, completeness, parity feature, atomic replacement và hành vi validation Phase 0. |
| Calendar/completeness | `PASS_WITH_NOTES` | Completeness theo symbol, ngày Việt Nam, source, timeframe và session quan sát; report có count, first/last timestamp, duplicate và gap classification. Không dùng 226 candle làm chuẩn universal. |

## Validation chỉ đọc có thể chạy lại

```bash
PHASE0_DATABASE_URL='postgresql://...' python scripts/phase0_validate_schema.py
python scripts/phase0_reconcile_sample.py --symbol SSI --date 2026-08-03 --timeframe 1d
python scripts/phase0_reconcile_sample.py --symbol SSI --date 2026-08-03 --timeframe 15m --timestamp 2026-08-03T02:00:00Z
```

Command schema bắt buộc PostgreSQL `default_transaction_read_only=on`. Command reconcile chỉ SELECT có giới hạn. Kết quả là `PASS`, `FAIL` hoặc `UNKNOWN`; thiếu evidence không thành false pass. Payload check đọc tối đa 100 row, chấp nhận NULL lịch sử và trả `UNKNOWN` nếu không tìm thấy sample khác NULL. Tolerance số mặc định là `1e-6` cho absolute/relative.

## Giả định calendar và completeness

- Diễn giải session/ngày theo `Asia/Ho_Chi_Minh`, giữ timestamp UTC timezone-aware khi lưu.
- Ngày trong tuần không tự động là ngày giao dịch; cần phân biệt empty, holiday, halt, phiên rút ngắn và lỗi source khi evidence cho phép.
- Không dựng row ngày nghỉ, forward-fill candle hoặc đổi missing thành 0.
- Repo chưa có nguồn calendar/status sàn authoritative có version được duyệt. Trước khi có nguồn đó, ngày lễ trong tuần và phiên ngoại lệ có thể là `UNKNOWN`/warning thay vì false failure.
- Count candle thay đổi theo auction, thanh khoản, halt, phiên rút ngắn, convention timestamp và behavior SSI; 226 không phải expected count universal.

## Ảnh hưởng dữ liệu và migration

Closure này không apply migration, ghi production, ingest, gọi RPC replace, delete, rebuild feature hay backfill. `stock_raw_intraday.payload` lịch sử tiếp tục NULL nếu trước đây không capture. Không đổi formula feature nên không cần backfill feature.

## Rủi ro còn lại

1. Supabase CLI migration history có thể không phản ánh SQL apply thủ công; trước deployment sau phải kiểm tra schema deployed thay vì chỉ dựa history.
2. Evidence sau cần lưu exact symbol, ngày, timeframe, timestamp và output; owner validation dùng để đóng Phase 0 không cung cấp các identifier đó trong repo.
3. Chưa triển khai nguồn calendar/status phiên ngoại lệ authoritative, có version và được duyệt.
4. Live check SSI/Supabase cần credential ngoài; run offline phải báo `UNKNOWN`, không được nhận là live verification.

## Bước tiếp theo

Bắt đầu đặc tả Phase 1 cho quy tắc chiến lược dùng chung và backtest point-in-time.
