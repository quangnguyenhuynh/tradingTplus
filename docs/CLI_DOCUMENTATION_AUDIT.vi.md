# Báo cáo khôi phục tài liệu CLI

[English](CLI_DOCUMENTATION_AUDIT.md)

## Phạm vi và audit trước chỉnh sửa

Nguồn hành vi: dev `b5cb3276f367a0e50ded3c83967570f24b7480c6` (PR #178). Nguồn tài liệu lịch sử: `90a57b1b0a2eca80f04fbbe01f36b5d9856d3db5`. Checkout ban đầu ở mốc lịch sử, remote-tracking dev còn cũ; git fetch thất bại do proxy không kết nối. GitHub connector xác nhận dev mới. Snapshot được khôi phục bằng patch/object GitHub và kiểm tra hash blob/tree/commit trước khi checkout nhánh docs/restore-cli-ssi-v3. Không sửa code để tạo snapshot; diff được tính từ đúng commit dev.

Audit đã đối chiếu AGENTS, main/CLI parser/handler, registry/capability, entrypoint ingest/feature/research, script/parser, README hai ngôn ngữ, CURRENT_STATE, quyết định kiến trúc, mapping tái cấu trúc, workflow, schema/migration liên quan và test CLI/inspector. Runbook English còn danh sách lệnh ngắn; tiếng Việt chỉ tóm tắt và trỏ sang English. Mất hướng dẫn phạm vi, mode, side effect, troubleshooting, workflow foreign/research; domain README chung chung, link package bị lệch sau di chuyển.

Trước chỉnh sửa đã báo trong chat: khôi phục hai runbook tự đủ, cập nhật root/src/CLI/script/inspector và domain liên quan; tạo cặp audit này; chỉ Markdown; migration none, data none, backfill none; kiểm tra help, parser/plan offline, links, compile và tests. Không cần xác nhận thêm vì phạm vi tài liệu đã được cho phép.

## Phân loại ví dụ lịch sử

| Loại | Ví dụ / quyết định |
| --- | --- |
| Vẫn đúng | Feature daily/intraday từ clean, range/full/replace; foreign preview/dry-run/check/rank/history; index preview/feature; Analog/Screener parser còn tồn tại |
| Đúng sau cập nhật | Inspector chuyển sang scripts/inspectors/ssi_rest, kiểm tra v3 và selector hiện tại; script chuyển checks/previews/maintenance/capture; link domain theo ingest/contracts/providers/features/research |
| Lỗi thời vì retire | Lệnh source cũ, URL REST cũ, consumer credential và fallback; không khôi phục làm lệnh vận hành |
| Tạm chưa dùng được | Master sync/init, nguồn intraday/backfill, combined backfill, refill, streaming/orderbook, diagnostic phụ thuộc adapter đã tắt |
| Sai/chưa chứng minh | [--apply] literal trong bash; help cũ mô tả nguồn tắt; source auto như literal; exit 0 coi là đủ dữ liệu; claim persist validation Analog; live readiness/completeness chưa kiểm chứng |

## Mâu thuẫn và issue code để task riêng

1. daily mặc định weekday trước hôm nay; stock-eod/stock-daily/index-daily tính cả hôm nay. Plain daily dùng mã tường minh trực tiếp, EOD giao với master active.
2. Help các lệnh tắt vẫn mô tả ingest cũ; runtime preflight mới là nguồn đúng. Empty index_master gợi ý sync-master-data nhưng sync đang tắt.
3. scripts/previews/run_features.py ghi stock_features, không có dry-run/ngày; tên/vị trí gây hiểu nhầm. Không di chuyển/sửa script.
4. Streaming inspector chạy file trực tiếp bị inspect.py che module inspect chuẩn và circular import; help qua module invocation chạy được. Đánh dấu BLOCKED direct path; nghiệp vụ vẫn NOT_IMPLEMENTED.
5. Analog validate nhận --apply nhưng handler không persist analog_validation_runs. Không thể tuyên bố vòng đời validation/approval mới hoàn tất chỉ qua CLI. Inspect còn bắt --distance-threshold nhưng runtime bỏ qua theo top-k.
6. REST inspector log còn in đường dẫn data_contracts cũ; file thật ở contracts. page-index/page-size 0 bị thay bằng mặc định trước validation.
7. check_ssi_ingest_schema còn kỳ vọng một số cột index/foreign cũ; cần sửa diagnostic riêng, không đổi schema để khớp cột cũ.
8. Legacy SQL intraday value cập nhật rộng không scope, dùng close*volume; không phải ví dụ repair production an toàn.

## Phân loại thao tác và nội dung đã phục hồi

32 lệnh production, toàn bộ subcommand Analog cùng alias, tham số/default/required/choices; stock/index ingest và backfill; feature incremental/full/range/atomic replace; foreign đủ preview/dry-run/validate/ranking/history không calendar dependency; Screener V1/V2 và config/apply; Analog profile/history/validation/review/query/inspect/daily; inspector native/alias/range/paging/mapping; 13 Python CLI script và một artifact SQL. Helper module không phải CLI độc lập.

READ-ONLY SSI: REST inspector, index-preview. READ-ONLY DB: checks, feature preview/check, RPC foreign, preview screener, Analog đọc/dry-run (trừ dry-run profile local không cần DB). WRITE: raw/clean ingest, feature calculation, run_features, apply screener/config/Analog có gate, atomic replace. NOT_IMPLEMENTED: tám lệnh production và diagnostic/capture/streaming liên quan. Thay thế feature cần một mã/một timeframe/range; không chạy ví dụ ghi để kiểm tra tài liệu.

Link local đã đối chiếu tồn tại, sửa link feature/package sau di chuyển; giữ link English/Việt. Main runbook có cùng tham số và cùng ví dụ hai ngôn ngữ; tiếng Việt tự đủ thao tác. Không phục hồi source retire hay claim tự tạo tín hiệu giao dịch.

## Kiểm tra và kết quả

Dùng interpreter `.venv/bin/python`; Python hệ thống thiếu SDK Supabase/pytest nên lần thử đầu không chạy được. Sau khi dùng venv có sẵn, các kết quả dưới đã chạy offline. Không sửa dependency/project config.

```bash
.venv/bin/python main.py --help
.venv/bin/python -m compileall main.py src scripts tests
.venv/bin/python -m pytest -q tests/cli tests/inspectors
.venv/bin/python -m pytest -q
.venv/bin/python work/validate_docs.py
git diff --check
```

- PASS: compileall và kiểm tra whitespace.
- PASS: test CLI/inspector 122 passed.
- PASS: full suite 577 passed, 7 skipped (test PostgreSQL atomic replace cần TEST_DATABASE_URL).
- PASS: 140 ví dụ duy nhất parse offline, feature scope/replace validation và inspector request-plan/selector validation; không gọi service nghiệp vụ. Bao phủ 32 lệnh production và subcommand/alias Analog.
- PASS: link local của Markdown đã đổi tồn tại; cặp ngôn ngữ và ví dụ chính tương đương.
- PASS: 62/63 help/list invocation; bao gồm toàn bộ root/lệnh/subcommand, inspector list/run help và script có parser. check_supabase không có help parser, chỉ kiểm tra không truyền option, không chạy DB.
- FAIL có sẵn, BLOCKED: direct-path streaming inspector help (ImportError/circular import); module help PASS. Không sửa code theo giới hạn task.
- SKIPPED theo yêu cầu: mọi SSI/Supabase live read/write, persistence/completeness production, migration và backfill. Parser pass không chứng minh dữ liệu tồn tại hay đủ quyền tài khoản.

Script kiểm tra là scratch ở work/, không thuộc patch tài liệu. Sau đóng gói, scratch được chuyển ra /workspace/work/tradingTplus-documentation; lệnh trên ghi lại vị trí tại lúc thực thi.

## Tệp đã sửa

- `README.md`
- `README.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/CURRENT_STATE.md`
- `scripts/README.md`
- `scripts/README.vi.md`
- `scripts/capture/README.md`
- `scripts/capture/README.vi.md`
- `scripts/checks/README.md`
- `scripts/checks/README.vi.md`
- `scripts/inspectors/README.md`
- `scripts/inspectors/README.vi.md`
- `scripts/inspectors/ssi_rest/README.md`
- `scripts/inspectors/ssi_rest/README.vi.md`
- `scripts/inspectors/ssi_streaming/README.md`
- `scripts/inspectors/ssi_streaming/README.vi.md`
- `scripts/maintenance/README.md`
- `scripts/maintenance/README.vi.md`
- `scripts/previews/README.md`
- `scripts/previews/README.vi.md`
- `src/README.md`
- `src/README.vi.md`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/diagnostics/README.md`
- `src/diagnostics/README.vi.md`
- `src/features/README.md`
- `src/features/README.vi.md`
- `src/features/foreign/README.md`
- `src/features/foreign/README.vi.md`
- `src/features/index/README.md`
- `src/features/index/README.vi.md`
- `src/features/stock/README.md`
- `src/features/stock/README.vi.md`
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
- `src/research/analogs/README.md`
- `src/research/analogs/README.vi.md`
- `src/research/screener/README.md`
- `src/research/screener/README.vi.md`

## Tệp mới

- `docs/CLI_DOCUMENTATION_AUDIT.md`
- `docs/CLI_DOCUMENTATION_AUDIT.vi.md`

## Tác động và bước tiếp theo

Migration: none. Database impact: none (không bảng/index/hàng nào bị thay). Backfill: none. Rủi ro còn lại là quyền dịch vụ, schema đã triển khai, chất lượng/lịch sử dữ liệu chưa live-test và các issue code nêu trên. Bước tiếp theo: review patch tài liệu; tạo task code riêng cho streaming import và Analog validation persistence trước khi dùng luồng bị chặn.
