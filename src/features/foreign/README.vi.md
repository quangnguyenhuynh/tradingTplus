# src/features/foreign

[English](README.md)

## Feature và xếp hạng foreign EOD

Foreign V2 chỉ dùng các hàng `stock_daily` cùng mã theo trading_date, cửa sổ theo số hàng quan sát; không đọc/suy diễn calendar file. Foreign thiếu vẫn để thiếu. Chỉ ghi `stock_foreign_features_daily`, không sửa nguồn. Sửa lịch sử có thể ảnh hưởng cửa sổ sau; xem ngày bị ảnh hưởng trong report. Xem [đặc tả Foreign EOD](../../../docs/FOREIGN_EOD_FEATURES.vi.md).

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

[CLI](../../../docs/CLI_USAGE.vi.md)
