# Bằng chứng SSI v3 securitiesByBoard — 26–27/10/2026

[English](SSI_V3_MASTER_EVIDENCE.md)

Owner cung cấp kết quả chỉ đọc trong task, không kèm credential hay full response
nguyên văn:

| Request | HTTP | Dạng JSON | Count quan sát |
| --- | --- | --- | --- |
| GET /api/v3/data/securitiesByBoard?board=HOSE | 200 | array | 793 |
| GET /api/v3/data/securitiesByBoard?board=HNX | 200 | array | 410 |
| GET /api/v3/data/securitiesByBoard?board=UPCOM | 200 | array | 851 |

Tổng 2.054. Đây là mốc lịch sử để so sánh bất thường, không phải tổng cố định phải
khớp, metadata phân trang hay bằng chứng universe đầy đủ. Endpoint không cung cấp
total/pagination metadata. Chỉ dùng ba request trên, không thêm pageIndex/pageSize
và không fallback nguồn khác.

Tên field đã xác minh: symbol, symbolNameVi, symbolNameEn, board, stockType,
lotSize, listedShare, firstTradingDate, lastTradingDate, maturityDate,
cwUnderlyingSymbol, cwExercisePrice, cwExecutionRatio, icbCode, icbName, iIndex,
iNav, openInterest, settlementPrice. stockType quan sát: Stock, Bond, ETF Product,
Investment Fund; chấp nhận giá trị lạ/NULL. HNX có thể thiếu listedShare,
symbolNameEn và mô tả khác. UPCoM có ngày 2026/01/27; ngày optional rỗng là NULL.

Bằng chứng xác nhận request ba board và contract field được map; không xác nhận
mọi ngữ nghĩa field phụ, tổng thị trường authoritative, index definition,
membership hay v4/v5. Không tạo issuer, issue_date, tick fields giả.

Fixture tests/fixtures/data_preview/ssi_v3_master_contract_samples.json dùng giá trị
minh họa theo tên field/kiểu/ngày owner đã xác minh. Không phải payload SSI live
nguyên văn; không dựng lại 2.054 rows. Test HTTP giả lập chứng minh implementation,
không phải quan sát live mới. Fixture và inspector mapping PASS không chứng minh
market completeness.

Agent không gọi SSI live vì thiếu credential. Đã query catalog TradingTPus_DS chỉ
đọc, xác nhận primary key hai bảng và không có FK securities→symbols. Không write
Supabase, migration hay backfill giá.

[Policy guard và quy trình owner](../src/ingest/master/README.vi.md).

## Cutover master hợp nhất — 27/10/2026

Phần này thay thế hướng dẫn cũ sync symbols/securities độc lập: chỉ symbols là đích vật lý; securities là alias deprecated có warning, all chỉ chạy symbols một lần. Owner apply A expand/merge TRƯỚC deploy app; B retire riêng có approval, mặc định abort. Agent không apply production. VN50 GROWTH được loại đúng rule và đếm; HNX-request DERIVATIVES/Future giữ domain thật và inactive mặc định. Index vẫn BLOCKED; không backfill giá. [Runbook](../src/ingest/master/README.vi.md).
