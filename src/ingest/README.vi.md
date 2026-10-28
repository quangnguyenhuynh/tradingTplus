# src/ingest

## CLI EOD chuẩn — 28/10/2026

| Lệnh | Hành vi hiện có giữ nguyên |
| --- | --- |
| `stock-eod` | Ingest stock + daily completeness, lọc mã active |
| `stock-eod-backfill` | Backfill stock daily bao gồm hai đầu; không thêm completeness |
| `index-eod` | Ingest index daily raw/clean hiện có |
| `index-eod-backfill` | Backfill index daily bao gồm hai đầu hiện có |

Chỉ bốn tên trên dùng cho top-level EOD ingest/backfill stock/index.
Đã bỏ, không alias/redirect: `daily`, `stock-daily`, `stock-daily-backfill`,
`backfill-daily`, `index-daily`, `index-daily-backfill`, `index-backfill`.
Direct daily cũ có date/scope/completeness khác và đã nghỉ; stock-eod vẫn dùng
run_stock_eod_pipeline, không thay bằng daily_run. Mặc định EOD stock/index lấy
ngày trong tuần gần nhất tính cả hôm nay tại Việt Nam. Giữ validation, scope,
summary và exit code. Backfill giữ alias --from/--from-date, --to/--to-date.
PARTIAL vẫn có thể exit 0 theo _status_to_exit hiện có; không đổi policy.
Python API daily_run/run_daily_ingest/run_index_daily_ingest/backfill, dataset ID
stock_daily/index_daily và JSON flow cũ (index-daily, backfill-daily/index-backfill)
giữ nguyên. Dataset Inspector `stock-daily` không đổi. Stock/index tách riêng;
không tự tính feature/signal/backtest. Không migration/schema/data/backfill bắt buộc.
Không chạy ví dụ WRITE để thử tên. Báo cáo tên/alias lịch sử phía dưới đã được
phần này thay thế.

```bash
python main.py stock-eod --help
python main.py stock-eod-backfill --help
python main.py index-eod --help
python main.py index-eod-backfill --help
```


Backfill EOD chuẩn: `stock-eod-backfill`, `index-eod-backfill`; đã bỏ alias EOD cũ. Chỉ intraday giữ `stock-intraday-backfill` / `backfill-intraday`. Hành vi runner không đổi.

[English](README.md)

## Ingest Stock Daily

**Historical / đã nghỉ:** `daily`: WRITE — raw/clean ingest. Đọc SSI v3 `securitiesSummary`, giữ payload/hash nguồn trong `stock_raw_daily`, validate rồi lưu `stock_daily` chuẩn. Không chạy completeness hay tính toán tầng sau. Bỏ ngày: chọn ngày trong tuần gần nhất trước hôm nay tại Việt Nam. Mã tường minh được dùng trực tiếp; bỏ mã: lấy master active đã lưu. Removed top-level command; use stock-eod with its existing active scope and completeness.

`stock-eod`: WRITE — raw/clean ingest kèm completeness chỉ cho daily. Mã tường minh được giao với master active, báo các mã không biết/inactive bị bỏ. Không có mã active trả FAILED. Ngày mặc định là ngày trong tuần gần nhất tính cả hôm nay tại Việt Nam, khác `daily`. Completeness đối chiếu thời điểm lần chạy và source kỳ vọng. Không ingest index/intraday, không ghi dataset foreign-trading riêng, không tự chạy feature. Trường đếm/summary intraday cũ không có nghĩa là đã ingest intraday.

Ngày ghi nguồn tường minh ở cuối tuần/tương lai bị từ chối. Ngày nghỉ trả rỗng được báo, không tạo hàng giả. Cần cả credential SSI và Supabase.

```bash
python main.py stock-eod --help
python main.py stock-eod --help
python main.py stock-eod --help
python main.py stock-eod 19/10/2026 --symbols SSI
python main.py stock-eod 19/10/2026 --symbols SSI HPG --data-source ssi_v3
python main.py stock-eod --symbols SSI
python main.py stock-eod --symbols SSI
python main.py stock-eod 19/10/2026 --symbols SSI HPG
```
## Backfill lịch sử Stock Daily

WRITE — raw/clean ingest: `stock-eod-backfill` bắt buộc `--from`, `--to`; alias là `--from-date`, `--to-date`. Mã tùy chọn áp dụng cho từng ngày; bỏ mã dùng master active trong mỗi lần ingest. Có thể chỉ định `--data-source ssi_v3`; bỏ tùy chọn chọn adapter v3 ready, không truyền chuỗi `auto`.

Runner bỏ cuối tuần, từ chối khoảng đảo/tương lai, ghi trạng thái OK/PARTIAL/FAILED từng ngày và tiếp tục khi có lỗi. Khoảng chỉ có cuối tuần là OK không làm gì. Không chạy completeness: đọc summary từng ngày và kiểm tra chỉ đọc với phạm vi riêng. Chạy lại có thể cập nhật clean và giữ bằng chứng raw. Không tính feature hay gọi combined backfill đang tắt.

```bash
python main.py stock-eod-backfill --help
python main.py stock-eod-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI HPG --data-source ssi_v3
```
## Preview và ingest Index Daily

`index-preview`: READ-ONLY — SSI API request, không đọc/ghi DB. Bắt buộc `--date` hoặc cặp `--from`, `--to`, cùng `--indexes` là chuỗi mã phân cách dấu phẩy. Mặc định in bảng chuẩn hóa; `--raw` in JSON raw, `--json` in JSON chuẩn hóa; hai cờ loại trừ nhau. Không có tùy chọn production `--data-source` tại đây.

`index-eod`: WRITE — raw/clean ingest từ SSI v3 `indexSummary` vào `index_raw_daily`, sau đó `index_daily` đã validate. Ngày positional tùy chọn mặc định là ngày trong tuần gần nhất tính cả hôm nay tại Việt Nam. `--indexes` nhận một/nhiều mã cách bằng khoảng trắng. Bỏ mã chọn `index_master` active; mã tường minh phải có trong master (có thể chọn hàng inactive). Master rỗng hoặc mã không biết gây ValueError, thường exit CLI 2. Thông báo lỗi gợi ý sync-master-data nhưng dataset SSI v3 của lệnh còn BLOCKED: kiểm tra master đã lưu và xử lý bằng bảo trì được cho phép riêng. Preview không cần master.

```bash
python main.py index-preview --help
python main.py index-eod --help
python main.py index-preview --date 2026-10-19 --indexes VNINDEX --raw
python main.py index-preview --from 2026-10-01 --to 2026-10-19 --indexes VNINDEX,HNXINDEX --json
python main.py index-eod 19/10/2026 --indexes VNINDEX HNXINDEX --data-source ssi_v3
python main.py index-eod 19/10/2026
```
## Backfill và completeness Index Daily

`index-eod-backfill`: WRITE — raw/clean ingest, bắt buộc cặp ngày bao gồm hai đầu `--from`/`--to` (alias `--from-date`/`--to-date`), tùy chọn mã `--indexes` theo master và source. Bỏ cuối tuần, báo số ngày/index; không tự tính feature.

`index-check`: READ-ONLY — database read, kiểm tra raw/clean của ngày positional tùy chọn và mã trong master. Mặc định ngày trong tuần trước hôm nay, khác index-daily. Chỉ cần credential DB. Có raw không chứng minh có clean hợp lệ. Sau ingest OK/PARTIAL vẫn phải đọc bằng chứng validation/completeness.

```bash
python main.py index-eod-backfill --help
python main.py index-check --help
python main.py index-eod-backfill --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX HNXINDEX
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
