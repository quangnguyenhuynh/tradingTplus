# src/ingest/stock_daily

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

[CLI](../../../docs/CLI_USAGE.vi.md)
