# src/ingest/index_daily

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

## Preview và ingest Index Daily

`index-preview`: READ-ONLY — SSI API request, không đọc/ghi DB. Bắt buộc `--date` hoặc cặp `--from`, `--to`, cùng `--indexes` là chuỗi mã phân cách dấu phẩy. Mặc định in bảng chuẩn hóa; `--raw` in JSON raw, `--json` in JSON chuẩn hóa; hai cờ loại trừ nhau. Không có tùy chọn production `--data-source` tại đây.

`index-eod`: WRITE — raw/clean ingest từ SSI v3 `indexSummary` vào `index_raw_daily`, sau đó `index_daily` đã validate. Ngày positional tùy chọn mặc định là ngày trong tuần gần nhất tính cả hôm nay tại Việt Nam. `--indexes` nhận một/nhiều mã cách bằng khoảng trắng. Bỏ mã chọn `index_master` active; mã tường minh phải có trong master (có thể chọn hàng inactive). Master rỗng hoặc mã không biết gây ValueError, thường exit CLI 2. Thông báo lỗi gợi ý sync-master-data nhưng lệnh đó đang tắt: kiểm tra master đã lưu và xử lý bằng bảo trì được cho phép riêng. Preview không cần master.

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

[CLI](../../../docs/CLI_USAGE.vi.md)
