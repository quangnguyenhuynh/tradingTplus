# src/features/foreign

ACTIVE: giữ nguyên công thức foreign EOD và bảng stock_foreign_features_daily.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `calculator.py`
- `calendar.py`
- `loader.py`
- `persistence.py`
- `service.py`
- `validator.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.

---

# Foreign EOD Feature V2

Pipeline derived độc lập này chỉ đọc `stock_daily`. Cửa sổ là 5/10/20 dòng cuối của chính mã theo `trading_date`; không đọc hoặc suy calendar. Xem [`docs/FOREIGN_EOD_FEATURES.vi.md`](../../docs/FOREIGN_EOD_FEATURES.vi.md) về công thức, quality, CLI, migration và triển khai.
