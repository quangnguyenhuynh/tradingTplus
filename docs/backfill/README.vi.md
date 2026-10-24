# CLI backfill dữ liệu nguồn

[English](README.md) · [Tham chiếu CLI](../CLI_USAGE.vi.md)

## Tên canonical và tương thích

Lệnh backfill dữ liệu nguồn dùng `<dataset>-backfill`. Alias cũ tiếp tục được hỗ trợ, không có ngày bỏ. Argparse giữ cách gọi; CLI chuẩn hóa đúng ba tên canonical về key handler hiện có. Không đổi module Python, runner public, tham số, thuật toán, status/exit hoặc `flow` JSON. Không in cảnh báo deprecation lên stdout.

| CLI canonical | Alias tương thích | Hành vi hiện tại / runner hiện có |
| --- | --- | --- |
| `stock-daily-backfill` | `backfill-daily` | ACTIVE / WRITE → `run_daily_backfill_pipeline()` |
| `stock-intraday-backfill` | `backfill-intraday` | DISABLED / NOT_IMPLEMENTED trước handler |
| `index-daily-backfill` | `index-backfill` | ACTIVE / WRITE → `run_index_backfill_pipeline()` |

## Lệnh dữ liệu nguồn đang active

Ví dụ dưới ghi raw/clean, dành cho operator có scope được ủy quyền rõ ràng, không dùng xác minh offline. Stock dùng `--symbols`; index dùng `--indexes`. Giữ alias ngày `--from-date`/`--to-date`, source tùy chọn, cận ngày bắt buộc, default scope và validation. Không thêm cờ `--write`/`--dry-run`.

```bash
python main.py stock-daily-backfill --from 01/10/2026 --to 20/10/2026 --symbols SSI HPG --data-source ssi_v3
python main.py index-daily-backfill --from 01/10/2026 --to 20/10/2026 --indexes VNINDEX HNXINDEX --data-source ssi_v3
```

Stock Daily dùng SSI v3 `securitiesSummary`, chỉ ghi `stock_raw_daily`/`stock_daily`. Index Daily dùng SSI v3 `indexSummary`, resolve master index hiện có và ghi `index_raw_daily`/`index_daily`. Source không hỗ trợ, kể cả ssi_v2, vẫn bị từ chối; không fallback. Giữ xử lý khoảng bao gồm hai đầu, từ chối tương lai/đảo ngược, xử lý tuần tự, bỏ/báo cuối tuần, range chỉ cuối tuần là OK no-op. Ghi lỗi theo ngày và tiếp tục ngày sau như cũ. Không tự chạy completeness, tính feature, signal/backtest.

Symbol stock trim/uppercase/loại trùng theo thứ tự đầu tiên. Index trim/loại trùng không phân biệt hoa thường, giữ cách viết đầu tiên, rồi resolve persisted master hiện có. Bỏ scope giữ hành vi master cũ; explicit scope rỗng là sai. JSON daily giữ `flow=backfill-daily`, day flow `backfill-daily-day`; index giữ `flow=index-backfill`, day flow `index-backfill-day`. Exit giữ 0 OK/PARTIAL, 1 FAILED/runtime failure, 2 argument/source sai.

## Route tắt và ranh giới manual pilot

`stock-intraday-backfill` và `backfill-intraday` chỉ là tên dự phòng. Cả hai trả JSON FAILED/NOT_IMPLEMENTED có kiểm soát, exit 1, không nạp handler, tạo client SSI/Supabase, gọi manual ingest hay feature. Source ssi_v3 tường minh được kiểm theo stock_intraday bằng lookup preview không tạo adapter rồi vẫn chặn; source không hỗ trợ giữ exit 2. Không nâng readiness hoặc bật workflow. Chỉ kiểm tra help:

```bash
python main.py stock-intraday-backfill --help
python main.py backfill-intraday --help
```

`backfill` kết hợp, `refill`, `intraday-ingest`, streaming-ingest và master vẫn tắt. Mô tả cũ về thực thi combined/refill hoặc hỗ trợ SSI v2 đã được thay bằng trạng thái hiện tại này. Wrapper Python deprecated `backfill(...)` vẫn delegate combined pipeline đang unavailable, không phải lựa chọn active thay split daily backfill.

Pilot `stock-intraday` thủ công đúng một mã/ngày có guard giữ nguyên, không phải alias backfill. Không chuyển route khoảng ngày dự phòng qua pilot. Không đổi tên hay hành vi `features`, `features-daily`, `features-intraday`, `foreign-features-backfill`, `index-features-backfill`; feature rebuild/backfill là pipeline riêng.

## Xác minh offline và tác động

Help cho tên mới/cũ không cần credential, không gọi service:

```bash
python main.py --help
python main.py stock-daily-backfill --help
python main.py backfill-daily --help
python main.py index-daily-backfill --help
python main.py index-backfill --help
```

Đổi tên không cần migration schema/bảng/dữ liệu, thay lịch sử hoặc backfill. Task không đổi schedule/workflow hay chạy production. Giữ hành vi raw/clean/validation/features hiện có; không sửa dữ liệu lịch sử chỉ để đổi CLI.

## Báo cáo triển khai — 23/10/2026

**Trạng thái: COMPLETE.** Đã kiểm tra lại dev `d81e0eff1bb63c7234c3a2c10cdfd88ace29ef17` (PR #183). CLI trước đây trộn tên stock dạng tiền tố backfill và index-backfill; nay có tên canonical theo dataset, giữ toàn bộ alias cũ. Runbook cũ còn mô tả intraday/combined/refill đang chạy và hỗ trợ SSI v2 tường minh; bản trên sửa đúng trạng thái hiện tại, không đổi khả năng thực thi code.

Triển khai: parser đăng ký canonical kèm argparse aliases, giữ argument action/default. Main CLI chỉ chuẩn hóa stock-daily-backfill → backfill-daily, stock-intraday-backfill → backfill-intraday, index-daily-backfill → index-backfill trước source preflight/disabled guard/dispatch. Handler maintenance/index và runner public giữ nguyên. Không sửa ingest/API/DB/validation/feature/thuật toán backfill; giữ flow JSON, exit convention và không in cảnh báo deprecation lên stdout.

Source preflight intraday backfill tường minh resolve đúng stock_intraday thay vì stock_daily, dùng lookup nonproduction không tạo adapter. Source ssi_v3 vẫn bị guard NOT_IMPLEMENTED/exit 1; ssi_v2 không hỗ trợ vẫn exit 2. Không source vẫn chặn trước handler. Hai tên đều unavailable; combined backfill/refill/intraday-ingest/streaming-ingest vẫn tắt. Không đổi manual pilot stock-intraday, lệnh feature, registry readiness hoặc schedule. Daily/index tên mới/cũ gọi cùng runner với ngày/source/default scope giống nhau; giữ khác biệt normalize stock/index hiện có.

### Lệnh test và kết quả

```bash
.venv/bin/python -m pytest -q tests/cli/test_cli_refactor.py
.venv/bin/python -m pytest -q tests/cli/test_capability_retirement.py
.venv/bin/python -m pytest -q tests/pipeline/test_backfill_pipeline.py
.venv/bin/python -m pytest -q tests/ingest/test_index_daily_pipeline.py
.venv/bin/python -m pytest -q tests/cli/test_backfill_names.py
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall main.py src scripts tests
.venv/bin/python main.py --help
.venv/bin/python main.py stock-daily-backfill --help
.venv/bin/python main.py stock-intraday-backfill --help
.venv/bin/python main.py index-daily-backfill --help
.venv/bin/python main.py backfill-daily --help
.venv/bin/python main.py backfill-intraday --help
.venv/bin/python main.py index-backfill --help
git diff --check
```

Bốn suite bắt buộc hiện có pass lần lượt **25 / 25 / 10 / 16**; capability suite thêm case tên canonical bị tắt. Test mới naming/routing/help/docs: **74 passed**. Full regression: **978 passed, 7 skipped**. Compile/diff và bảy help invocation pass offline. Bảy test replacement RPC PostgreSQL hiện có skip vì TEST_DATABASE_URL chưa cấu hình. Không thử live backfill, fetch nguồn hay xác minh DB; runner active dùng fake và guard client/service/manual pilot. Các giả định test ban đầu về wrap help alias/cách viết index đã sửa theo hành vi thật; test cuối pass.

Test mới cover parser canonical/legacy, alias cận ngày, required bounds/flag sai, dataset/source rejection, scope/source mặc định, argument runner và flow JSON, exit OK/PARTIAL/FAILED giữ nguyên, help không credential và intraday chặn trước handler/manual/API/DB. Regression CLI, manual pilot, Daily/Index/features, disabled capability và backfill cũ tiếp tục pass.

### File sửa

- `README.md`
- `README.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/STOCK_INTRADAY_PIPELINE.md`
- `docs/STOCK_INTRADAY_PIPELINE.vi.md`
- `docs/backfill/README.md`
- `docs/backfill/README.vi.md`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/cli/__init__.py`
- `src/cli/parser.py`
- `src/ingest/README.md`
- `src/ingest/README.vi.md`
- `src/ingest/index_daily/README.md`
- `src/ingest/index_daily/README.vi.md`
- `src/ingest/maintenance/README.md`
- `src/ingest/maintenance/README.vi.md`
- `src/ingest/master/README.md`
- `src/ingest/master/README.vi.md`
- `src/ingest/stock_daily/README.md`
- `src/ingest/stock_daily/README.vi.md`
- `src/ingest/stock_intraday/README.md`
- `src/ingest/stock_intraday/README.vi.md`
- `src/ingest/streaming/README.md`
- `src/ingest/streaming/README.vi.md`
- `src/ingest/workflows/README.md`
- `src/ingest/workflows/README.vi.md`
- `tests/cli/test_capability_retirement.py`

### File tạo

- `tests/cli/test_backfill_names.py`

### Tác động DB, rủi ro và bước tiếp

Migration/schema/bảng/dữ liệu thay đổi: **NONE**. Cần backfill: **NO**. Không chạy migration. Không đổi module Python ingest, provider/DB/feature hoặc workflow; chỉ cập nhật README song ngữ liên quan. Quyết định kiến trúc/evidence report lịch sử giữ tên cũ dưới nghĩa lịch sử/alias vẫn tương thích.

**No live SSI ingestion or Supabase database writes were executed.**

Giới hạn chủ ý: intraday backfill chỉ có tên dự phòng, chưa triển khai; flow JSON giữ tên legacy, không suy từ tên CLI mới. Daily/index active vẫn ghi theo contract hiện có và không thêm cờ dry-run/write. Live backfill ngoài phạm vi, không nhận là đã xác minh. Bước tiếp: review/merge PR chỉ đổi naming này, ưu tiên canonical trong hướng dẫn operator mới, giữ alias, và cần task/ủy quyền riêng trước intraday range ingest. Không cần chạy lại production để dùng tên mới.
