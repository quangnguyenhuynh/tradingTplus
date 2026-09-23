# Feature và báo cáo khối ngoại EOD

Luồng độc lập là `stock_daily -> lệnh foreign feature -> stock_foreign_features_daily -> RPC -> CLI/web/mobile`. Ingest không tự gọi feature. Nguồn duy nhất là field DailyStockPrice đã chuẩn hóa trong `stock_daily`; không có REST endpoint ForeignTrading công khai riêng.

## Công thức V2 và cửa sổ theo dòng

Với mã S và ngày đích D, calculator chỉ lấy dòng của S có `trading_date <= D`, từ chối trùng `(symbol, trading_date)`, sắp xếp theo ngày rồi lấy N dòng cuối gồm D. Vì vậy **N phiên là N dòng `stock_daily` của chính mã**, không phải N ngày lịch, weekday, lịch hợp nhất toàn sàn hay ngày suy từ mã khác. Preview/daily target yêu cầu S có đúng dòng D. Backfill chỉ tạo output cho ngày S có source.

Với W=5 hoặc 20, B/S/N/V là giá trị mua, bán, net đã kiểm tra và `total_traded_value`:

* net value = `SUM(N)`; activity value = `SUM(B+S)`;
* net ratio = `SUM(N)/SUM(V)`; activity ratio = `SUM(B+S)/(2*SUM(V))`;
* số phiên mua/bán ròng đếm N>0/N<0;
* change 5D lấy ratio của 5 dòng hiện tại trừ 5 dòng liền trước, không chồng lấn; cần 10 dòng chứ không cần 20.

Tiền là VND, ratio là fraction. Dòng đã tồn tại nhưng field NULL/sai vẫn chiếm vị trí; không bỏ dòng để kéo dòng cũ hơn, không đổi NULL thành 0 và không forward-fill. Metric bị ảnh hưởng là NULL và có reason. Mẫu số 0/sai làm ratio NULL. Đủ 5 nhưng thiếu 20 vẫn tính metric 5; metric 20 báo `INSUFFICIENT_HISTORY`. Lỗi volume không làm mất metric value nếu input value vẫn hợp lệ.

Formula version 2 fingerprint mã, ngày đích, phiên bản và toàn bộ field value/volume của tối đa 20 dòng thực sự ảnh hưởng metric/quality. Fingerprint không chứa calendar, mã khác hay dòng cũ ngoài cửa sổ. Upsert ghi cả NULL cho mọi metric theo khóa `(symbol, trading_date)`, nên không giữ nhầm giá trị cũ.

## Warm-up, incremental và check

Backfill lấy tối đa 19 dòng trước `--from` **riêng từng mã** và chỉ ghi trong range yêu cầu. Incremental rà 20 dòng nguồn cuối mỗi mã đến ngày yêu cầu, phát hiện thiếu feature, sai version hoặc đổi fingerprint. Sửa lịch sử ngoài phạm vi rà cần backfill riêng. Một dòng sửa có thể ảnh hưởng chính nó và tối đa 19 dòng sau của cùng mã.

Preview, target, backfill, incremental và check dùng chung loader/calculator. Check chỉ đọc, đối chiếu source với version/fingerprint V2; không ingest, sửa hay backfill. Loader source và feature đã lưu đều phân trang đủ với thứ tự ổn định.

`--calendar-file` tạm thời chỉ còn để tương thích. Lệnh trả cảnh báo `DEPRECATED_CALENDAR_FILE_IGNORED`, tuyệt đối không mở file và file không thể đổi kết quả. V2 không còn `WINDOW_UNVERIFIED`.

## CLI

```bash
python main.py foreign-features-preview --help
python main.py foreign-features-backfill --help
python main.py foreign-features-preview --symbol SSI --date 28/08/2026 --show-source
python main.py foreign-features-backfill --from 03/08/2026 --to 28/08/2026 --symbols SSI --dry-run
python main.py foreign-features-backfill --from 03/08/2026 --to 28/08/2026 --symbols SSI
python main.py foreign-features-check --from 03/08/2026 --to 28/08/2026 --symbols SSI
python main.py foreign-rank --date 28/08/2026 --ranking accumulation --window 5 --symbols SSI --top 20
python main.py foreign-rank --date 28/08/2026 --ranking emerging --window 5 --sort value --symbols SSI --top 20
python main.py foreign-symbol --symbol SSI --date 28/08/2026 --lookback 20
python main.py foreign-features-daily --date 28/08/2026 --symbols SSI SHB --dry-run
```

Preview/check/rank/history không ghi. `--show-source` hiển thị đúng source calculator dùng và ngày của từng cửa sổ/hai nhóm change. `--dry-run` của daily/backfill chạy loader, calculator, validation thật nhưng không gọi persistence; output có `would_write` và `written=0`. Bỏ `--dry-run` thì daily/backfill mới ghi bảng derived.

## Migration RPC và triển khai

Bảng được tạo ở `20260907_create_stock_foreign_features_daily.sql`. Cần triển khai `20260923_foreign_features_symbol_rows_v2.sql` để thay hai RPC nhưng giữ tên/chữ ký/quyền. Ranking V2 không trộn feature cũ. Emerging value/ratio tính trực tiếp 5 dòng hiện tại và 5 dòng trước từ source, nên cần 10 dòng hợp lệ và feature V2 ngày đích, không cần feature ngày trước hoặc đủ 20 dòng. Ranking vẫn cố định cùng ngày yêu cầu. History đánh dấu row khác V2 là `STALE_FORMULA`.

Chỉ pull code **không** cập nhật RPC trong DB. Thứ tự khuyến nghị: phối hợp deploy migration V2 và code; preview scope nhỏ; backfill V2 có phạm vi; chạy check; rồi kiểm tra ranking/history. Không tự apply production hoặc ghi production. Nếu `stock_daily` đã đúng thì không cần ingest lại. SQL verification và hướng dẫn rollback nằm cuối migration.
