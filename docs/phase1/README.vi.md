# Phase 1

## Hợp đồng đang dùng

Historical Analog là hướng Phase 1 duy nhất đang active. Nền backend EOD V1 đã
được triển khai; profile hiện vẫn là draft với distance threshold null nên final
validation, approval và query production vẫn bị chặn.

- [Spec tiếng Việt](HISTORICAL_ANALOG_SPEC.vi.md)
- [Spec tiếng Anh](HISTORICAL_ANALOG_SPEC.md)
- [Package đã triển khai](../../src/analogs/README.vi.md)
- [Migration database](../../migrations/20260809_create_historical_analog_core_eod_v1.sql)

Spec và artifact thực thi của hướng rule cũ đã bị xóa trong cleanup 10/08/2026.
Các migration lịch sử được giữ làm deployment history; cleanup migration sẽ xóa
sáu bảng đã retire khi được apply.

## Ranh giới

Phase 1 chỉ so một mã với lịch sử hợp lệ trước đó của chính mã ở cùng checkpoint
và không gom mã khác khi thiếu mẫu. Command ingest/feature không tự gọi Analog,
signal, alert, ranking, NAV hoặc execution.
