# Bộ test

Unit test, contract test, regression, CLI, migration-text và pipeline test chạy offline.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)
- Test validation: [`validation/README.vi.md`](validation/README.vi.md)

## Phạm vi kiểm tra

- Hợp đồng production CLI và exit code.
- Pipeline daily, intraday-ingest, EOD, one-day và streaming.
- SSI REST/streaming inspector.
- Mapping raw/clean và ý nghĩa intraday value.
- Feature engine aggregate, incremental/full và target date.
- Hành vi signal/backtest MVP ở nơi đã có test.
- Contract text của migration/schema.
- Validation daily, intraday và streaming.

## Command

```bash
python -m pytest -q tests/test_feature_engine.py
python -m pytest -q tests/test_cli_refactor.py tests/test_eod_pipeline.py
python -m pytest -q tests/validation
python -m pytest -q
python -m compileall main.py src scripts
```

## Quy tắc

- Chạy test nhỏ liên quan trước, sau đó chạy full suite khi phù hợp.
- Unit test không phụ thuộc credential SSI/Supabase thật nếu không được đánh dấu integration/smoke rõ ràng.
- Mock API và database bên ngoài.
- Test bình thường không được ghi dữ liệu production.
- Task chỉ đổi tài liệu vẫn phải kiểm tra path, command và link với repo hiện tại.
- Phân biệt lỗi có sẵn và lỗi do task tạo ra.

GitHub Actions chạy toàn bộ pytest khi có pull request và push vào `dev`.
