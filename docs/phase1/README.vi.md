# Tài liệu nghiên cứu Phase 1

Phase 1 bắt đầu lớp nghiên cứu downstream sau khi dữ liệu và feature Phase 0
được kiểm chứng. Các tài liệu trong thư mục này là hợp đồng thiết kế, chưa phải
hành vi code đang chạy.

## Tài liệu

| File | Mục đích |
| --- | --- |
| `RULE_BACKTEST_APPROVAL_SPEC.vi.md` | Spec tối thiểu cho việc thiết kế rule T+ hai bước, backtest lại và approve rule/version trước khi chạy signal thật. |
| `RULE_BACKTEST_APPROVAL_SPEC.md` | Bản English của hợp đồng rule/backtest/approval. |
| `CODEX_TASK_RULE_BACKTEST_APPROVAL.vi.md` | Task tự đầy đủ để giao Codex triển khai framework rule/backtest approval. |
| `CODEX_TASK_RULE_BACKTEST_APPROVAL.md` | Bản English của task Codex. |

## Phạm vi

Rule Phase 1 phải nằm sau pipeline `features` hiện có:

```text
features
  -> replay rule hai bước
  -> bằng chứng backtest
  -> approve strategy
  -> scan signal thật bằng rule approved
```

Ingest, validation, clean market data và feature computation vẫn tách riêng.
Không khôi phục bảng hoặc code legacy signal/backtest đã bị retire.
