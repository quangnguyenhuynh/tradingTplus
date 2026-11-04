# Truy cập database

## Numeric daily chính xác — 04/11/2026

Daily mapping/contract 3.0.0: tiền/giá/level/phần trăm dùng Decimal, quantity
rời rạc dùng integer chính xác. Stock policy 1.1.0 giữ phần lẻ tiền với warning
FRACTIONAL_MONETARY_VALUE/PARTIAL; Index giữ pipeline riêng, reject numeric sai.
Cần owner apply **migration mới** `20261104_daily_numeric_precision.sql`; không
sửa migration V1 cũ, không tự rewrite/backfill/features.
Diagnostic chỉ đọc: `python main.py daily-numeric-quality --dataset stock_daily --identifiers TCB --date 12/03/2025`
(đổi dataset index_daily/identifiers VNINDEX cho Index).
[Bảng field, transport, audit, SQL/deploy/rollback và lệnh owner](../../docs/DAILY_NUMERIC_PRECISION.vi.md).
Hướng dẫn integer-money/float của daily trước đây được policy này thay thế; các ghi nhận test lịch sử vẫn là evidence tại thời điểm chạy.


## Stock Daily Data Quality V1 — 03/11/2026

SSI v3 Stock Daily dùng VALID/PARTIAL/REJECTED, quarantine optional lỗi thành NULL,
giữ RAW bất biến và log hiện tại/lịch sử. Cần owner apply migration
`20261103_stock_daily_quality_v1.sql` trước writer mới; status lịch sử giữ NULL.
Diagnostic chỉ đọc mới: `python main.py stock-eod-quality --symbols TCB --from 05/03/2026 --to 06/03/2026 --raw-clean-missing`.
Giữ tên `stock-eod`/`stock-eod-backfill`; không tự backfill/features.
[Policy, triển khai, SQL kiểm tra và rerun đúng scope](../../docs/STOCK_DAILY_QUALITY_V1.vi.md).


Supabase client và các helper persistence của repository.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## File chính

- `client.py`: khởi tạo Supabase client và cung cấp helper đọc/insert/upsert theo bảng.
- `__init__.py`: export package.

## Trách nhiệm

- Đọc master, raw, clean, feature và snapshot data cho các pipeline hiện tại.
- Ghi record theo đúng hợp đồng table và conflict key.
- Trả lỗi có ngữ cảnh thay vì nuốt lỗi database.
- Lấy credential từ biến môi trường và không in ra log.

## Ranh giới

- Package này không định nghĩa hoặc tự migrate schema.
- Thay đổi schema thuộc [`migrations/`](../../migrations/README.vi.md).
- Trước khi thêm `upsert`, phải xác nhận unique index tương ứng tồn tại.
- Không fallback sang cách ghi tạo duplicate chỉ để job tiếp tục chạy.
- Không đổi field thị trường thiếu thành 0 nếu chưa có quy tắc đã kiểm chứng.

## Test

Unit test nên mock Supabase client. Smoke test live mặc định read-only và chạy qua các script như `scripts/checks/check_supabase.py` và `scripts/checks/check_ssi_ingest_schema.py`.

## Adapter Phase 1

Adapter database kiểu rule cũ đã bị xóa. Historical Analog dùng repository và
migration bảy bảng riêng, không ghi raw, clean hoặc feature.

## Cutover master hợp nhất — 27/10/2026

Phần này thay thế hướng dẫn cũ sync symbols/securities độc lập: chỉ symbols là đích vật lý; securities là alias deprecated có warning, all chỉ chạy symbols một lần. Owner apply A expand/merge TRƯỚC deploy app; B retire riêng có approval, mặc định abort. Agent không apply production. VN50 GROWTH được loại đúng rule và đếm; HNX-request DERIVATIVES/Future giữ domain thật và inactive mặc định. Index vẫn BLOCKED; không backfill giá. [Runbook](../ingest/master/README.vi.md).
