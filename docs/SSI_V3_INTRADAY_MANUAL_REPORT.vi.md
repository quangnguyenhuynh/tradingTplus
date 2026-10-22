# Báo cáo triển khai pilot intraday SSI v3 thủ công có guard

[English](SSI_V3_INTRADAY_MANUAL_REPORT.md) · [Runbook owner](STOCK_INTRADAY_PIPELINE.vi.md)

## Trạng thái và audit

**COMPLETE cho code và xác minh offline khả thi; owner live verification còn chờ.** Đã kiểm tra lại base dev `3598a675bc1e3105b92a773d18ce0db4baab3136` (PR #181). Trước sửa, CLI/workflow chặn stock-intraday, registry chỉ preview. Helper upsert có thể ghi đè và ước tính value thiếu nên không an toàn cho pilot. Schema/migration hiện có đủ payload raw, sequence/default ID, unique raw `(symbol,time,data_hash)`, khóa clean `(symbol,timeframe,time)`, value BIGINT nullable và partition/RPC tháng. Quy tắc ước tính value cũ trong AGENTS được yêu cầu nguồn SSI v3 mới của owner thay thế cho riêng path này.

## Thay đổi và capability

Chỉ mở `stock-intraday` hiện có dưới MANUAL_PILOT: mặc định/--dry-run chỉ đọc, --write mới ghi. Bắt buộc đúng một mã/ngày DD/MM/YYYY hoặc YYYY-MM-DD; từ chối thiếu scope, ngày tương lai, range, ALL/wildcard/comma, nhiều mã kể cả lặp cùng mã trước khi tạo client. --data-source ssi_v3 resolve dataset stock_intraday, không phải daily.

Đã audit consumer registry: daily/index vẫn dùng production adapter; inspector và manual riêng mới resolve preview. Registry không đổi readiness/factory; generic fetch stock_intraday không mở. intraday-ingest, backfill-intraday, backfill kết hợp, refill, streaming-ingest và master vẫn tắt; workflow không có schedule. Không tự chạy feature/signal/backtest.

Dùng lại preview adapter, client, mapping, paging và 204 đã xác minh. Mọi source candle phải map/validate đúng mã/ngày Việt Nam, OHLCV và value nguyên nguồn không thiếu; fetch toàn ngày từ trang 1, không rỗng, không duplicate/mixed. Tăng/giảm dần hợp lệ; sort view validation cho nguồn giảm dần, không sửa raw hoặc che anomaly thật. Contract nullable chung không đổi.

Eligibility chỉ đọc đúng symbol, cần cả status/intraday_status active; báo rõ control chặn, không auto-active hoặc mở rộng universe. DB preflight đúng mã/ngày, paging kèm exact count. Ngày Việt Nam 2026-10-20 tương ứng UTC [2026-10-19T17:00:00Z,2026-10-20T17:00:00Z). Dry-run thiếu DB báo NOT_RUN_NO_CREDENTIALS, planned chưa biết, write_ready=false.

## Raw/clean, xung đột và phục hồi

Raw dùng cột hiện có symbol/time/OHLCV/data_hash/payload/source/fetched_at, giữ JSON candle gốc bao gồm chuỗi tradingDate/value; source=ssi_v3. SHA-256 từ JSON canonical của source, không có audit time/header. Không chèn candle giả hoặc terminal envelope; DB tự cấp ID theo sequence/default hiện có.

Clean dùng cột hiện có symbol/timeframe/time/OHLCV/value/created_at, chỉ 1m. Value nguyên SSI giữ đúng; không đi qua helper ước tính hoặc upsert ghi đè legacy. Clean giống canonical skip, không gán provenance giả; khác giá trị hoặc timestamp clean thừa chặn toàn preflight. Raw cùng key nhưng khác source/payload/raw values chặn, kể cả payload lịch sử thiếu. Raw hash khác giữ nguyên, tách count toàn scope và count khớp.

Dựng đủ hai payload, validate toàn nguồn và preflight cả hai lớp trước mutation. Chèn raw rồi đọc lại xác nhận; kiểm tra lại eligibility và clean conflict. Chỉ sau đó tạo đúng tháng UTC cần clean mới bằng RPC partition hiện có. Dry-run/no-op rerun không tạo partition. Cả hai lớp dùng ignore_duplicates=True (DO NOTHING), không ghi đè hàng lịch sử/đồng thời. Final readback đối chiếu mọi raw key/payload/source và clean count/timestamp/canonical values. Rerun skip hàng giống, bổ sung clean thiếu sau raw-only success, không cleanup/delete/force.

Hai HTTP write không atomic xuyên bảng. Lỗi sau mutation attempt trả PARTIAL/nonzero; trước đó BLOCKED/nonzero, có failed stage và hướng phục hồi. Mỗi DB request một lần thử ở tầng ứng dụng; đếm batch đã xác nhận và đánh dấu count chưa chắc khi insert lỗi có thể đã commit. Kiểm tra đúng scope rồi rerun. Structural gap/session warning là quan sát; completeness luôn UNVERIFIED, không suy từ HTTP success hay 226 hàng.

## Kiểm thử

```bash
.venv/bin/python -m pytest -q tests/ingest/test_manual_intraday.py
.venv/bin/python -m pytest -q tests/ingest/test_manual_intraday.py tests/cli/test_manual_intraday_cli.py
.venv/bin/python -m pytest -q tests/data_preview tests/ingest tests/pipeline tests/cli tests/validation
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall main.py src scripts tests
.venv/bin/python main.py --help
.venv/bin/python main.py stock-intraday --help
git diff --check
```

Manual ban đầu 48 pass; phiên bản cuối có **73 test manual/CLI mới**. Nhóm regression áp dụng: **489 passed**. Full suite cuối: **791 passed, 7 skipped**. Compile/help/parser/diff sạch. Full run trước sáu edge case cuối đạt 785/7. Test mới hoàn toàn fake API/DB: paging/204, HTTP/API/truncation, invalid OHLCV/value/mapping, duplicate/mixed/descending, dry-run không mutation/partition, UTC scope, eligibility, DB count truncation, raw payload/source/hash, value zero/khác close*volume, xung đột lịch sử/cross-source/đồng thời, idempotency, failure sau batch đã xác nhận, raw-only recovery và readback count/value mismatch. Test workflow và disabled command giữ boundary; regression Daily/Index/features pass.

Bảy test PostgreSQL replacement RPC hiện có skip vì TEST_DATABASE_URL chưa cấu hình. Không có postgres/initdb/psql; Docker daemon socket bị từ chối nên không có disposable PG khả dụng. Không chạy live SSI/Supabase smoke do thiếu credential; chờ owner, không báo live pass. Đã đối chiếu [Supabase Python upsert](https://supabase.com/docs/reference/python/upsert), chữ ký SDK cài sẵn và changelog HTML (markdown fetch không được hỗ trợ).

## Tác động DB và rủi ro còn lại

Migration: **none**; không bảng/cột/index/RPC mới. Dữ liệu live bị tác động: **none**; sửa lịch sử/backfill: **none**. Không đổi formula hoặc dữ liệu feature/research.

**No live Supabase writes were executed by Codex.**

Runtime cần constraint/permission/partition RPC và timezone triển khai phù hợp, kết nối SSI/Supabase. Thiếu constraint/RPC lỗi sẽ chặn, không fallback insert/overwrite. Khóa raw thiếu source nên collision cần owner điều tra. Clean không có provenance; không chứng nhận hàng giống lịch sử vốn từ SSI v3. Không tự sửa conflict. Writer khác vẫn có thể đổi dữ liệu sau readback; dừng chúng khi pilot. Bar start/end, turnover semantics độc lập và coverage toàn phiên chưa xác minh. Không quy tắc 226, không tạo phút thiếu/backfill tự động. Preflight giới hạn 10.000 hàng đúng scope, source paging theo bound client hiện có.

## Owner xác minh và bước tiếp theo

Sau merge, cấu hình credential local, hai master status đã active:

```bash
python main.py stock-intraday 20/10/2026 --symbols SSI
# Chỉ owner sau khi xem dry-run, eligibility và conflict preflight:
python main.py stock-intraday 20/10/2026 --symbols SSI --write
# Owner lặp lại cùng lệnh --write để xác minh không thêm hàng.
```

Giữ ba JSON, yêu cầu nguồn/paging pass, không reject/duplicate/lỗi value/conflict, raw/clean readback PASS, lần lặp số chèn bằng 0; completeness vẫn UNVERIFIED. Nếu PARTIAL, kiểm tra đúng scope/conflict rồi rerun; không xóa lịch sử để ép pass. Bước tiếp theo: owner xác minh pilot này; multi-symbol/backfill cần task và ủy quyền riêng.

## File sửa

- `README.md`
- `README.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/CURRENT_STATE.md`
- `docs/SSI_V3_INTRADAY_PREVIEW_REPORT.md`
- `docs/SSI_V3_INTRADAY_PREVIEW_REPORT.vi.md`
- `docs/STOCK_INTRADAY_PIPELINE.md`
- `docs/STOCK_INTRADAY_PIPELINE.vi.md`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/cli/__init__.py`
- `src/cli/parser.py`
- `src/cli/stock.py`
- `src/ingest/stock_intraday/README.md`
- `src/ingest/stock_intraday/README.vi.md`
- `src/ingest/workflows/README.md`
- `src/ingest/workflows/README.vi.md`
- `src/ingest/workflows/stock_intraday.py`
- `src/providers/ssi/README.md`
- `src/providers/ssi/README.vi.md`
- `src/providers/ssi/adapters/intraday_preview.py`
- `tests/cli/test_capability_retirement.py`
- `tests/pipeline/test_stock_intraday_pipeline.py`

## File tạo

- `src/ingest/stock_intraday/manual.py`
- `tests/cli/test_manual_intraday_cli.py`
- `tests/ingest/test_manual_intraday.py`
- `docs/SSI_V3_INTRADAY_MANUAL_REPORT.md`
- `docs/SSI_V3_INTRADAY_MANUAL_REPORT.vi.md`
