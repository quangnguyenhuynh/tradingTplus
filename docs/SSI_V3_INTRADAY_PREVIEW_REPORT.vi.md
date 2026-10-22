# Báo cáo sửa timestamp, terminal 204 và value SSI v3 Intraday

[English](SSI_V3_INTRADAY_PREVIEW_REPORT.md) · [Runbook](STOCK_INTRADAY_PIPELINE.vi.md)

## Status: COMPLETE cho phạm vi sửa preview và kiểm tra offline

Đã sửa ba lỗi, replay hai candle thật cùng terminal envelope do chủ sở hữu cung cấp, và chạy toàn bộ test offline. Agent live rerun: **NOT_RUN** vì môi trường không có SSI credential. Chưa nhận toàn bộ capture 226 hàng nên không khẳng định đã tự map lại 226/226. Production readiness: **false**, ingest/schedule/backfill vẫn tắt. Ý nghĩa bar-start/end và official matched turnover còn chưa xác minh độc lập, không bị che giấu bởi kết quả test.

Base dev: `09f0ea4a1d2f5d920f3f7eb2be4eb1d7a9375831` (PR #180 đã merge). Nhánh sửa: `fix/ssi-v3-intraday-evidence`. Audit trước sửa đã đọc AGENTS, entrypoint/CLI, client/adapter/mapper/transform/dictionary/engine, contract/schema/migration, validator, estimator, DB fallback, inspector và test/tài liệu. Yêu cầu mới của chủ sở hữu thay rõ ràng quy ước estimate cũ chỉ cho SSI v3 preview; không đổi behavior legacy hoặc historical provenance.

## Nguyên nhân và trước/sau

| Vấn đề | Trước | Sau |
| --- | --- | --- |
| Timestamp | Đọc ohlc.time, thiếu time vì response thật có tradingDate; naive bị từ chối | ohlc.tradingDate, format YYYY/MM/DD HH:mm:ss được diễn giải tường minh Asia/Ho_Chi_Minh rồi UTC |
| 204 | Client chặn API code 204, decoder đòi array | Chỉ OHLC 1m cho decoder kiểm tra envelope code 204 + No Content; terminal rỗng hợp lệ sau consistency checks |
| Value | derived + calculate_trade_value(close, volume) | ohlc.value → parse Decimal/integer chính xác; không estimate/fallback |

Mapping version 1.2.0-preview; contract version 1.0.0 và field/schema/nullable/key giữ nguyên. definitions.json chỉ sửa mô tả ngữ nghĩa nguồn/historical; không đổi type/required/nullable. Engine truyền tên field nguồn trong context để transform riêng SSI chỉ diễn giải naive market-local ở tradingDate; alias time cũ vẫn cần offset. Generic aware-only transform không mở rộng sang dataset khác.

## Bằng chứng và raw-to-clean

Fixture `tests/fixtures/data_preview/ssi_v3_intraday_ssi_2026-10-20_owner_samples.json` chép đúng hai object candle thật và envelope terminal từ yêu cầu người dùng; không có secret hay log đầy đủ. Wrapper array/page và test biến đổi ghi rõ synthetic. Không tạo thêm 224 hàng để giả làm capture thật.

| Raw tradingDate | Canonical UTC | Raw close | Raw volume | Raw value → clean int |
| --- | --- | --- | --- | --- |
| 2026/10/20 14:45:00 | 2026-10-20T07:45:00Z | 19950 | 2626600 | 52400670000 → 52400670000 |
| 2026/10/20 14:29:00 | 2026-10-20T07:29:00Z | 19850 | 129000 | 2560650000 → 2560650000 |

Replay offline: raw 2, mapped 2, rejected 0, duplicate 0; raw/strings/thứ tự giảm dần giữ nguyên. Hai trang synthetic mỗi trang bọc một candle thật rồi terminal 204 tạo 3 request/3 trang nhận; trang ngắn không dừng sớm, pagination_complete=true, termination=provider_no_content_204. Không thêm nến auction hoặc dịch phút. Nhận format local có phần lẻ đến microsecond và ISO offset đã hỗ trợ, giữ nguyên instant/giây/phần lẻ. Ngày sai/thiếu/ngoài request hoặc identity lệch vẫn bị từ chối.

Chủ sở hữu báo cho riêng ngày SSI 2026-10-20: 226 raw/unique, 23 trang không rỗng, terminal 24, 135 sáng + 90 chiều + một 14:45, mọi hàng có value và tình cờ bằng close × volume. Các số này được lưu như **quan sát do chủ sở hữu cung cấp**, không phải kết quả replay đầy đủ của agent hoặc invariant completeness. Equality không phải quy tắc tính value.

## Value: giữ nguồn, null và lỗi

Canonical value là **SSI-reported intraday candle value**; không tự chứng nhận official matched turnover. Không đổi đơn vị hay áp dụng scale. Parse trực tiếp integer/chuỗi decimal có giá trị nguyên bằng Decimal, không đi qua float; giữ số lớn trên 2^53 và tối đa 2^63−1 chính xác. Float/bool, non-finite, số lẻ, âm, tràn hoặc chuỗi sai bị từ chối, raw giữ nguyên. Zero là zero. Thiếu/NULL/rỗng giữ canonical NULL, warning SOURCE_VALUE_MISSING, không estimate hoặc đổi zero.

Test **synthetic** close=19950, volume=100, value=1994000 chứng minh clean.value=1994000, khác 1995000 từ công thức. Test monkeypatch estimator để fail nếu preview gọi nó. Đây không phải candle thị trường thật.

Report tách source_value_present_count (nguồn cung cấp khác null/rỗng), source_value_numeric_valid_count (parse pass), source_value_mapped_count (candidate giữ được), missing/invalid count và source_value_semantics_verified=false. Có value từ API, giữ đúng trong mapping, validate số hợp lệ và xác minh nghĩa thị trường độc lập là bốn việc khác nhau. Warning thiếu value ngoài display sample vẫn hiện.

## Terminal 204 và lỗi giữ nguyên

Chấp nhận code integer/string 204 cùng No Content, không payload không rỗng/không hỗ trợ hay marker lỗi mâu thuẫn. First-page 204 → EMPTY; sau trang có data → kết thúc. Giữ envelope raw và số trang request/nhận. Vẫn kiểm tra pageIndex, totalRecord/pagesCount trước đó, số hàng cuối, thay đổi metadata, trang lặp/đảo lại, duplicate, short-page continuation và max-pages. 204 mâu thuẫn/malformed hoặc 400/401/403/500/lỗi provider khác không được coi là no-data. Daily/Index không được nhận exemption 204 của OHLC 1m.

Completeness luôn UNVERIFIED, độc lập pagination_complete. Descending order được giữ và ghi nhận; warning của view tăng dần/phiên/gap không cho phép sửa dữ liệu hay tạo nến. Source-value thiếu không làm mất giá trị nullable; invalid value từ chối riêng hàng bị lỗi.

## Persistence chưa bật: rủi ro chính xác cần xử lý sau

`src/database/client.py:upsert_intraday()` hiện tính lại value qua calculate_trade_value khi thiếu/NULL. Không sửa method hay consumer của nó. Preview không gọi persistence này, test chặn DB. Trước production promotion cần guard riêng nguồn v3 mang nguyên value, giữ NULL mà không fallback, từ chối value sai và test chứng minh không có recomputation. Không chỉ truyền NULL vào helper hiện tại. Không xóa fallback toàn cục hoặc sửa historical estimate khi chưa audit consumer. Sửa lịch sử cần task có scope ngày/mã/provenance và cho phép riêng.

Schema vẫn stock_raw_intraday (symbol,time,data_hash; original payload/source), stock_intraday (symbol,timeframe,time, monthly partitions, value BIGINT nullable). Migration thêm payload dùng tên raw_intraday cũ, migration chuẩn hóa sau đổi stock_raw_intraday; không có lý do sửa schema/đổi key ở task preview.

Migration: **none**. Ghi DB / thay dữ liệu production / sửa lịch sử: **none**. Backfill: **none**. Không feature/signal/backtest, không bật schedule hay capability production.

## Tệp sửa

- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/DATA_CONVENTIONS.md`
- `docs/DATA_CONVENTIONS.vi.md`
- `docs/SSI_V3_INTRADAY_PREVIEW_REPORT.md`
- `docs/SSI_V3_INTRADAY_PREVIEW_REPORT.vi.md`
- `docs/STOCK_INTRADAY_PIPELINE.md`
- `docs/STOCK_INTRADAY_PIPELINE.vi.md`
- `scripts/inspectors/ssi_rest/README.md`
- `scripts/inspectors/ssi_rest/README.vi.md`
- `scripts/inspectors/ssi_rest/inspect.py`
- `src/contracts/README.md`
- `src/contracts/README.vi.md`
- `src/contracts/definitions.json`
- `src/contracts/engine.py`
- `src/contracts/intraday_preview.py`
- `src/contracts/mappings/ssi_v3.json`
- `src/contracts/transforms.py`
- `src/ingest/stock_intraday/README.md`
- `src/ingest/stock_intraday/README.vi.md`
- `src/intraday_value.py`
- `src/providers/ssi/README.md`
- `src/providers/ssi/README.vi.md`
- `src/providers/ssi/adapters/intraday_preview.py`
- `src/providers/ssi/clients/rest_v3.py`
- `tests/data_preview/test_intraday_preview.py`

## Tệp mới

- `tests/data_preview/test_intraday_evidence_fix.py`
- `tests/fixtures/data_preview/ssi_v3_intraday_ssi_2026-10-20_owner_samples.json`

## Lệnh test thực thi và kết quả

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q tests/data_preview` | 148 passed |
| `.venv/bin/python -m pytest -q tests/inspectors` | 64 passed |
| `.venv/bin/python -m pytest -q tests/data_contracts` | 17 passed |
| `.venv/bin/python -m pytest -q tests/validation` | 57 passed |
| `.venv/bin/python -m pytest -q tests/ingest` | 81 passed |
| `.venv/bin/python -m pytest -q tests/cli` | 58 passed |
| `.venv/bin/python -m pytest -q` | 718 passed, 7 skipped |
| `.venv/bin/python -m compileall main.py src scripts tests` | PASS |
| `git diff --check` | PASS |

7 test PostgreSQL atomic replace skip vì thiếu TEST_DATABASE_URL. Full suite gồm Daily/Index regression, feature và capability-retirement; không sửa test feature hay code Daily/Index. Test cũng kiểm tra 204 không mở rộng sang Daily/Index, chặn DB trong preview và chứng minh không gọi estimator. Fixture thật chỉ chứa mẫu được cung cấp; 67 case mới cùng các test cũ điều chỉnh theo value nguồn. Không có database write smoke test hay live SSI PASS giả.

## Lệnh để chủ sở hữu xác minh chỉ đọc tiếp theo

```bash
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --full-json
```

Có thể xem xét task manual ingest riêng sau khi review raw/clean đầy đủ của owner, chốt guard persistence chống tính lại value/NULL và kiểm tra schema/provenance/partition đã triển khai. Chưa được bật manual production trong task này; registry/CLI/workflow giữ nguyên. Bước tiếp theo chính xác: chạy hai lệnh trên với credential local, xác nhận terminal 204 và source-value counts, rồi chủ sở hữu duyệt evidence cho task promotion tách biệt.

Kiểm tra tài liệu cuối: 25 ví dụ inspector parse/request-plan pass, mọi link local đã sửa tồn tại. Kiểm tra tự động xác nhận chỉ đổi metadata mô tả contract, không đổi DB client/schema/registry/CLI gate/workflow hay test feature.
