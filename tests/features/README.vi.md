# Test feature

Test offline cho hợp đồng feature daily và intraday deterministic.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## File

| File | Phạm vi |
| --- | --- |
| `test_feature_engine.py` | Ownership nguồn daily/intraday, aggregation, bucket đã đóng, indicator, baseline, context nullable, persistence và compatibility router. |
| `test_feature_range_backfill.py` | Validation range inclusive, warm-up window, giới hạn output và chạy backfill daily/intraday. |
| `test_feature_timeframe_policy.py` | Chính sách chỉ lưu `1d`, `15m`, `60m` và từ chối ghi feature `1m`/`5m`. |
| `test_issue99_contract.py` | Regression về cô lập symbol, phép tính liên tục, timestamp và đồng bộ schema/migration. |

Các test giữ ranh giới Phase 0: `1d` đọc `stock_daily`; feature intraday
aggregate nến clean 1 phút từ `stock_intraday` mà không ghi nến nguồn timeframe
cao hơn; ingest không chạy feature; feature không chạy signal hoặc backtest.

## Chạy test

```bash
python -m pytest -q tests/features
```

Test dùng fake/mock và không ghi dữ liệu production.
