# src/features

[English](README.md)

## Feature kỹ thuật cổ phiếu

Cả ba route đều WRITE — feature calculation vào `stock_features`, khóa `(symbol,timeframe,time)`. Không cần credential SSI. `1d` đọc `stock_daily`; `15m`, `60m` aggregate clean 1m `stock_intraday` trong bộ nhớ cùng ngữ cảnh giá daily. Chỉ persist bucket đã đóng. `stock_intraday` vẫn chỉ lưu 1m. Không hỗ trợ persist feature `1m`, `5m`. Tắt ingest nguồn không ngăn tính feature trên lịch sử intraday đã có.

`features` là router tương thích: tùy chọn `--date`, `--mode incremental|full` (mặc định incremental), mã tùy chọn, timeframe mặc định `15m 60m 1d`; không có range/replace. `features-daily` luôn chọn 1d. `features-intraday` mặc định `15m 60m`, hỗ trợ `--as-of` dạng `HH:MM` giờ Việt Nam hoặc timestamp có timezone. Không ghép as-of với khoảng ngày. Hai route tách nguồn bắt buộc ngày đích, cặp khoảng ngày hoặc full mode.

Incremental dùng watermark riêng mỗi stream và warm-up giới hạn (daily năm năm; intraday 250 phiên quan sát, không phải ngày lịch). Không có đầu ra mới có thể là OK không làm gì. Khoảng ngày chạy backfill bao gồm hai đầu. Full tính lại/upsert lịch sử đã chọn, không xóa; có thể tốn nhiều RAM, không ghép ngày/range. Sửa dữ liệu nguồn không tự vô hiệu feature cũ.

**WRITE — explicit rebuild có thể phá hủy dữ liệu:** replace và rebuild-clean cùng thay thế atomic một phạm vi. Bắt buộc đúng một mã, một timeframe được persist và hai đầu khoảng; không wildcard/ALL, không `--date`. Tính/validate bộ thay thế không rỗng trước, sau đó RPC service-role hiện có xóa và ghi lại đúng phạm vi. Xác nhận nguồn/warm-up đủ, đối soát mẫu, lưu bằng chứng trước/sau trước khi chạy. Không có cờ dry-run. Replace intraday phải chỉ định đúng một timeframe; mặc định hai timeframe bị từ chối.

```bash
python main.py features --help
python main.py features-daily --help
python main.py features-intraday --help
python main.py features --date 19/10/2026 --symbols SSI HPG --timeframes 1d
python main.py features-daily --date 19/10/2026 --symbols SSI
python main.py features-daily --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py features-daily --mode full --symbols SSI
python main.py features-intraday --date 19/10/2026 --symbols SSI --timeframes 15m 60m --as-of 14:30
python main.py features-intraday --from 01/10/2026 --to 19/10/2026 --symbols SSI --timeframes 60m
python main.py features-daily --mode replace --symbols SSI --from 01/10/2026 --to 19/10/2026
python main.py features-intraday --mode rebuild-clean --symbols SSI --timeframes 15m --from 01/10/2026 --to 19/10/2026
```
## Feature và xếp hạng foreign EOD

Foreign V2 chỉ dùng các hàng `stock_daily` cùng mã theo trading_date, cửa sổ theo số hàng quan sát; không đọc/suy diễn calendar file. Foreign thiếu vẫn để thiếu. Chỉ ghi `stock_foreign_features_daily`, không sửa nguồn. Sửa lịch sử có thể ảnh hưởng cửa sổ sau; xem ngày bị ảnh hưởng trong report. Xem [đặc tả Foreign EOD](../../docs/FOREIGN_EOD_FEATURES.vi.md).

Preview (`--symbol`, `--date`, tùy chọn `--show-source`/`--json`) và check (`--from`, `--to`, tùy chọn `--symbols`): READ-ONLY — database read. Daily/backfill: WRITE — feature calculation trừ khi có `--dry-run`, khi đó chỉ tính/validate không persist. Daily bắt buộc ngày, nhận `--mode target|incremental` (mặc định target); backfill bắt buộc hai ngày. Bỏ mã dùng phạm vi active từ DB. `--calendar-file` chỉ là tham số tương thích đã deprecated và bị bỏ qua, không phải điều kiện chạy.

`foreign-rank`, `foreign-symbol`: READ-ONLY — database RPC (`get_foreign_ranking`, `get_foreign_symbol_history`). Rank bắt buộc ngày/ranking; ranking gồm attention, accumulation, distribution, emerging. Window 1/5/20 (mặc định 5), sort value/ratio (value); tùy chọn market, symbols, top (20), offset (0). History bắt buộc một mã/ngày, lookback mặc định 20. RPC/schema phải có sẵn; exit 0 không xác nhận có hàng hoặc dữ liệu mới. Đọc quality, coverage, freshness trước khi diễn giải thứ hạng.

```bash
python main.py foreign-features-preview --symbol SSI --date 19/10/2026 --show-source
python main.py foreign-features-daily --date 19/10/2026 --symbols SSI HPG --dry-run
python main.py foreign-features-daily --date 19/10/2026 --symbols SSI --mode target
python main.py foreign-features-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI --dry-run
python main.py foreign-features-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py foreign-features-check --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py foreign-rank --date 19/10/2026 --ranking attention --window 1 --symbols SSI HPG --top 20
python main.py foreign-rank --date 19/10/2026 --ranking accumulation --window 5 --sort value --symbols SSI HPG --top 20
python main.py foreign-rank --date 19/10/2026 --ranking distribution --window 20 --sort ratio --top 20
python main.py foreign-rank --date 19/10/2026 --ranking emerging --window 5 --sort value --top 20
python main.py foreign-symbol --symbol SSI --date 19/10/2026 --lookback 20
```
## Feature chỉ số

Domain feature index độc lập đọc `index_daily`, lưu `index_features_daily` theo `(index_code,trading_date)`. Chỉ cần DB, không gọi SSI. Preview/check: READ-ONLY — database read. Daily/backfill: WRITE — feature calculation. Preview/daily bắt buộc `--date`; backfill/check bắt buộc `--from`, `--to` (không có alias dài cho ngày tại đây). `--indexes` tùy chọn nhận mã master cách bằng khoảng trắng; bỏ chọn master active. Dùng tối đa 250 phiên clean trước đó để warm-up. Không tạo OHLC hay phiên thiếu; cửa sổ chưa đủ giữ null. Đọc các ngày raw thiếu clean/thiếu feature trước khi chạy lại phạm vi chính xác.

```bash
python main.py index-features-preview --date 19/10/2026 --indexes VNINDEX
python main.py index-features-daily --date 19/10/2026 --indexes VNINDEX HNXINDEX
python main.py index-features-backfill --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX HNXINDEX
python main.py index-features-check --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX
```

[CLI](../../docs/CLI_USAGE.vi.md)
