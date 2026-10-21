# src/ingest/index_daily

[English](README.md)

## Preview và ingest Index Daily

`index-preview`: READ-ONLY — SSI API request, không đọc/ghi DB. Bắt buộc `--date` hoặc cặp `--from`, `--to`, cùng `--indexes` là chuỗi mã phân cách dấu phẩy. Mặc định in bảng chuẩn hóa; `--raw` in JSON raw, `--json` in JSON chuẩn hóa; hai cờ loại trừ nhau. Không có tùy chọn production `--data-source` tại đây.

`index-daily`: WRITE — raw/clean ingest từ SSI v3 `indexSummary` vào `index_raw_daily`, sau đó `index_daily` đã validate. Ngày positional tùy chọn mặc định là ngày trong tuần gần nhất tính cả hôm nay tại Việt Nam. `--indexes` nhận một/nhiều mã cách bằng khoảng trắng. Bỏ mã chọn `index_master` active; mã tường minh phải có trong master (có thể chọn hàng inactive). Master rỗng hoặc mã không biết gây ValueError, thường exit CLI 2. Thông báo lỗi gợi ý sync-master-data nhưng lệnh đó đang tắt: kiểm tra master đã lưu và xử lý bằng bảo trì được cho phép riêng. Preview không cần master.

```bash
python main.py index-preview --help
python main.py index-daily --help
python main.py index-preview --date 2026-10-19 --indexes VNINDEX --raw
python main.py index-preview --from 2026-10-01 --to 2026-10-19 --indexes VNINDEX,HNXINDEX --json
python main.py index-daily 19/10/2026 --indexes VNINDEX HNXINDEX --data-source ssi_v3
python main.py index-daily 19/10/2026
```
## Backfill và completeness Index Daily

`index-backfill`: WRITE — raw/clean ingest, bắt buộc cặp ngày bao gồm hai đầu `--from`/`--to` (alias `--from-date`/`--to-date`), tùy chọn mã `--indexes` theo master và source. Bỏ cuối tuần, báo số ngày/index; không tự tính feature.

`index-check`: READ-ONLY — database read, kiểm tra raw/clean của ngày positional tùy chọn và mã trong master. Mặc định ngày trong tuần trước hôm nay, khác index-daily. Chỉ cần credential DB. Có raw không chứng minh có clean hợp lệ. Sau ingest OK/PARTIAL vẫn phải đọc bằng chứng validation/completeness.

```bash
python main.py index-backfill --help
python main.py index-check --help
python main.py index-backfill --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX HNXINDEX
python main.py index-check 19/10/2026 --indexes VNINDEX
```

[CLI](../../../docs/CLI_USAGE.vi.md)
