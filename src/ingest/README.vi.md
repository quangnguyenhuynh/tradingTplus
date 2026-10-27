# src/ingest

Tên CLI canonical và alias tương thích (không có lịch bỏ alias): `stock-daily-backfill` → `backfill-daily`; `stock-intraday-backfill` → `backfill-intraday`; `index-daily-backfill` → `index-backfill`. Giữ tên CLI tương thích; daily/index không đổi. Intraday dùng contract range operator có guard. Stock Daily/Index Daily backfill ACTIVE / WRITE; Stock Intraday backfill có guard, chỉ operator, mặc định DRY_RUN, ghi cần --write và tối đa 50 cặp weekday; luồng tự động vẫn tắt.

[English](README.md)

## Ingest Stock Daily

`daily`: WRITE — raw/clean ingest. Đọc SSI v3 `securitiesSummary`, giữ payload/hash nguồn trong `stock_raw_daily`, validate rồi lưu `stock_daily` chuẩn. Không chạy completeness hay tính toán tầng sau. Bỏ ngày: chọn ngày trong tuần gần nhất trước hôm nay tại Việt Nam. Mã tường minh được dùng trực tiếp; bỏ mã: lấy master active đã lưu.

`stock-eod` và alias chính xác `stock-daily`: WRITE — raw/clean ingest kèm completeness chỉ cho daily. Mã tường minh được giao với master active, báo các mã không biết/inactive bị bỏ. Không có mã active trả FAILED. Ngày mặc định là ngày trong tuần gần nhất tính cả hôm nay tại Việt Nam, khác `daily`. Completeness đối chiếu thời điểm lần chạy và source kỳ vọng. Không ingest index/intraday, không ghi dataset foreign-trading riêng, không tự chạy feature. Trường đếm/summary intraday cũ không có nghĩa là đã ingest intraday.

Ngày ghi nguồn tường minh ở cuối tuần/tương lai bị từ chối. Ngày nghỉ trả rỗng được báo, không tạo hàng giả. Cần cả credential SSI và Supabase.

```bash
python main.py daily --help
python main.py stock-eod --help
python main.py stock-daily --help
python main.py daily 19/10/2026 --symbols SSI
python main.py daily 19/10/2026 --symbols SSI HPG --data-source ssi_v3
python main.py daily --symbols SSI
python main.py stock-eod --symbols SSI
python main.py stock-daily 19/10/2026 --symbols SSI HPG
```
## Backfill lịch sử Stock Daily

WRITE — raw/clean ingest: `stock-daily-backfill` bắt buộc `--from`, `--to`; alias là `--from-date`, `--to-date`. Mã tùy chọn áp dụng cho từng ngày; bỏ mã dùng master active trong mỗi lần ingest. Có thể chỉ định `--data-source ssi_v3`; bỏ tùy chọn chọn adapter v3 ready, không truyền chuỗi `auto`.

Runner bỏ cuối tuần, từ chối khoảng đảo/tương lai, ghi trạng thái OK/PARTIAL/FAILED từng ngày và tiếp tục khi có lỗi. Khoảng chỉ có cuối tuần là OK không làm gì. Không chạy completeness: đọc summary từng ngày và kiểm tra chỉ đọc với phạm vi riêng. Chạy lại có thể cập nhật clean và giữ bằng chứng raw. Không tính feature hay gọi combined backfill đang tắt.

```bash
python main.py stock-daily-backfill --help
python main.py stock-daily-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI HPG --data-source ssi_v3
```
## Preview và ingest Index Daily

`index-preview`: READ-ONLY — SSI API request, không đọc/ghi DB. Bắt buộc `--date` hoặc cặp `--from`, `--to`, cùng `--indexes` là chuỗi mã phân cách dấu phẩy. Mặc định in bảng chuẩn hóa; `--raw` in JSON raw, `--json` in JSON chuẩn hóa; hai cờ loại trừ nhau. Không có tùy chọn production `--data-source` tại đây.

`index-daily`: WRITE — raw/clean ingest từ SSI v3 `indexSummary` vào `index_raw_daily`, sau đó `index_daily` đã validate. Ngày positional tùy chọn mặc định là ngày trong tuần gần nhất tính cả hôm nay tại Việt Nam. `--indexes` nhận một/nhiều mã cách bằng khoảng trắng. Bỏ mã chọn `index_master` active; mã tường minh phải có trong master (có thể chọn hàng inactive). Master rỗng hoặc mã không biết gây ValueError, thường exit CLI 2. Thông báo lỗi gợi ý sync-master-data nhưng dataset SSI v3 của lệnh còn BLOCKED: kiểm tra master đã lưu và xử lý bằng bảo trì được cho phép riêng. Preview không cần master.

```bash
python main.py index-preview --help
python main.py index-daily --help
python main.py index-preview --date 2026-10-19 --indexes VNINDEX --raw
python main.py index-preview --from 2026-10-01 --to 2026-10-19 --indexes VNINDEX,HNXINDEX --json
python main.py index-daily 19/10/2026 --indexes VNINDEX HNXINDEX --data-source ssi_v3
python main.py index-daily 19/10/2026
```
## Backfill và completeness Index Daily

`index-daily-backfill`: WRITE — raw/clean ingest, bắt buộc cặp ngày bao gồm hai đầu `--from`/`--to` (alias `--from-date`/`--to-date`), tùy chọn mã `--indexes` theo master và source. Bỏ cuối tuần, báo số ngày/index; không tự tính feature.

`index-check`: READ-ONLY — database read, kiểm tra raw/clean của ngày positional tùy chọn và mã trong master. Mặc định ngày trong tuần trước hôm nay, khác index-daily. Chỉ cần credential DB. Có raw không chứng minh có clean hợp lệ. Sau ingest OK/PARTIAL vẫn phải đọc bằng chứng validation/completeness.

```bash
python main.py index-daily-backfill --help
python main.py index-check --help
python main.py index-daily-backfill --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX HNXINDEX
python main.py index-check 19/10/2026 --indexes VNINDEX
```
## Các lệnh tạm tắt

Các nhóm lệnh dưới giữ parser nhưng dừng trước khi nạp handler hoặc tạo client SSI/DB. Trả exit 1 và JSON status FAILED, error_type NOT_IMPLEMENTED. Source tường minh bị từ chối có thể trả exit 2 ở preflight trước đó. Help vẫn mô tả mục đích cũ, không chứng minh khả năng chạy.

| Lệnh | Mục đích trước đây | Adapter / dataset cần trong tương lai |
| --- | --- | --- |
| intraday-ingest | Ingest raw/clean nguồn 1m | Adapter v3 1m, pagination, timestamp, đơn vị đã xác minh; stock_intraday |
| backfill | Daily/intraday kèm check | Cùng adapter; stock_intraday; không chạy riêng phần daily |
| refill | Nguồn/check/feature một mã | Cùng adapter; stock_intraday; không chạy riêng daily/feature |
| streaming-ingest | Streaming giới hạn, ghi tùy chọn | Adapter protocol/auth/capture v3 đã xác minh; streaming |

Chụp orderbook cũng tắt đến khi có adapter streaming được xác minh; không tự tạo endpoint REST depth công khai. Raw/clean/master/feature/streaming lịch sử vẫn còn và dùng được theo contract. Gọi lệnh đang tắt không fallback, xóa hay sửa lịch sử. Dưới đây chỉ là help, không phải ví dụ chạy production thành công.

```bash
python main.py init --help
python main.py sync-master-data --help
python main.py intraday-ingest --help
python main.py stock-intraday --help
python main.py stock-intraday-backfill --help
python main.py backfill --help
python main.py refill --help
python main.py streaming-ingest --help
```

[CLI](../../docs/CLI_USAGE.vi.md)

## Master sync — cập nhật 27/10/2026

`sync-master-data` và alias `init` đã dùng orchestrator có guard, mặc định DRY_RUN. SSI v3 symbols/securities đã hỗ trợ refresh có guard ba board; index_master/index_components giữ BLOCKED. READY chỉ cho refresh không xóa có guard; market completeness authoritative vẫn UNVERIFIED. --write cần đúng một --dataset tường minh và provider READY. Giữ status operator; stock/index mới inactive. Không migration/backfill giá. [Runbook và báo cáo xác minh](master/README.vi.md).
