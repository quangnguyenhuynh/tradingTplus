# Tài liệu nghiên cứu Phase 1

Phase 1 là tầng historical analog và kiểm định phương pháp, nằm sau nền data và
feature Phase 0.

## Hợp đồng đang dùng

| File | Trạng thái | Mục đích |
| --- | --- | --- |
| [`HISTORICAL_ANALOG_SPEC.vi.md`](HISTORICAL_ANALOG_SPEC.vi.md) | Đã chốt thiết kế; chưa code | Matching cùng mã/cùng checkpoint, outcome H+, validation và runtime. |
| [`HISTORICAL_ANALOG_SPEC.md`](HISTORICAL_ANALOG_SPEC.md) | Đã chốt thiết kế; chưa code | Bản English. |

Nguyên tắc lõi: SSI chỉ dùng mẫu SSI lịch sử ở cùng checkpoint. Group chỉ là
nhãn của trạng thái feature tương tự, không phải pool nhiều mã. Thiếu mẫu cùng mã
thì trả `insufficient_sample`.

```text
snapshot feature an toàn thời điểm của một mã
  -> historical match cùng mã / cùng checkpoint
  -> phân phối outcome H+1 / H+3 / H+5
  -> validation theo thời gian
  -> phân tích hiện tại chỉ-đọc
```

Phase 1 tạo phân tích nghiên cứu, chưa tạo signal mua/bán, alert, ranking hoặc
gợi ý %NAV.

## Tài liệu đã bị thay thế

| File | Trạng thái |
| --- | --- |
| `RULE_BACKTEST_APPROVAL_SPEC.md` / `.vi.md` | Thiết kế fixed-rule cũ; chỉ giữ audit. |
| `CODEX_TASK_RULE_BACKTEST_APPROVAL.md` / `.vi.md` | Task lịch sử đã chạy; không dùng cho task mới. |

Repo vẫn có code strategy/rule, signal, backtest, CLI, schema, migration và test
cũ chạy được. Chúng **đã triển khai nhưng đang đóng băng**. Không chạy write
path, không approve production và không dùng metrics của chúng làm evidence cho
hợp đồng mới. Chỉ giữ để audit hoặc tái sử dụng có chủ đích cho đến khi có task
cleanup riêng được duyệt.

## Ranh giới

- Ingest, validation, feature, analog research, signal và alert delivery tiếp tục
  tách biệt.
- Không command Phase 1 nào tự gọi ingest hoặc feature.
- Tên bảng/CLI historical analog trong active spec mới là đề xuất, chưa phải hành
  vi code hiện tại.
- Task triển khai sau phải bắt đầu từ active spec và có migration, scope backfill,
  leakage test và evidence OOS theo thời gian.

## Core EOD V1 đã triển khai

Nền backend cho contract hẹp `TPLUS_ANALOG_CORE_EOD` V1 được mô tả tại
[`../../src/analogs/README.vi.md`](../../src/analogs/README.vi.md). Threshold vẫn
null/draft nên production result và approve bị chặn.
