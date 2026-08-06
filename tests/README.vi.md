# Bộ test

Bộ unit test, contract test, regression test, CLI test, migration-text test, validation test và pipeline test chạy offline cho Trading T+.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Cấu trúc

| Thư mục | Trách nhiệm |
| --- | --- |
| [`ingest/`](ingest/README.vi.md) | Mapping daily/intraday, tính value, tái sử dụng payload, điều phối ingest và truy vấn completeness. |
| [`features/`](features/README.vi.md) | Công thức feature, aggregate timeframe, chạy incremental/full và hợp đồng ghi dữ liệu. |
| [`validation/`](validation/README.vi.md) | Quy tắc validation daily, intraday và streaming. |
| [`streaming/`](streaming/README.vi.md) | Hành vi streaming ingest và contract migration. |
| [`inspectors/`](inspectors/README.vi.md) | Test cho SSI REST/streaming inspector chỉ đọc. |
| [`pipeline/`](pipeline/README.vi.md) | Điều phối EOD và hành vi dry-run. |
| [`cli/`](cli/README.vi.md) | Hợp đồng production CLI và entrypoint script. |
| [`strategies/`](strategies/README.vi.md) | Test registry/evaluator fixed-rule đang đóng băng. |
| [`signals/`](signals/README.vi.md) | Test approval/idempotency fixed-rule đang đóng băng. |
| [`backtest/`](backtest/README.vi.md) | Test replay/outcome/migration fixed-rule đang đóng băng. |

`conftest.py` thêm project root vào `sys.path` để import vẫn ổn định sau khi test được chia theo thư mục con.

## Lệnh thường dùng

```bash
python -m pytest -q tests/ingest
python -m pytest -q tests/features
python -m pytest -q tests/validation
python -m pytest -q tests/streaming tests/inspectors
python -m pytest -q tests/pipeline tests/cli
python -m pytest -q
python -m compileall main.py src scripts tests
```

## Quy tắc

- Chạy nhóm nhỏ liên quan trước, sau đó chạy full suite khi phù hợp.
- Test thông thường không phụ thuộc credential SSI hoặc Supabase thật.
- Mock API và database bên ngoài.
- Test không được ghi dữ liệu production.
- Mỗi lỗi data-quality production cần regression test deterministic.
- Không làm yếu validation chỉ để chấp nhận anomaly nguồn chưa giải thích.
- Test strategy/signal/backtest hiện tại mô tả research executable đang đóng
  băng; phải giữ pass nhưng không xem là acceptance evidence cho historical
  analog.
- Test Phase 1 mới phải theo active spec và chứng minh cùng mã/cùng checkpoint,
  input an toàn thời điểm và validation theo thời gian.
- Test validation Phase 0 cũng kiểm tra tolerance số, phân loại mismatch/unknown, policy payload lịch sử NULL, contract catalog schema và không gọi write/RPC.

GitHub Actions chạy toàn bộ pytest khi có pull request và push vào `dev`.
