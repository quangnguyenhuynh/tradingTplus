# Index Daily Feature V1

Package này là pipeline dữ liệu dẫn xuất riêng cho chỉ số thị trường. Pipeline
chỉ đọc hàng chuẩn hóa `index_daily` và chỉ ghi `index_features_daily`. Pipeline
không ingest SSI và không gọi stock feature, Analog, profile, signal, validation
hoặc backtest. Chỉ số chính ban đầu là `VNINDEX`; nếu bỏ `--indexes`, lệnh resolve
toàn bộ hàng trong `index_master` theo quy ước CLI index hiện tại.

## Schema và công thức

Identity là `(index_code, trading_date)`, có FK tới `index_master`. Các cột
`index_value`, `total_vol`, `total_val`, `breadth_total` dùng PostgreSQL `numeric`
để giữ độ chính xác; tỷ lệ và indicator xác định dùng `double precision`. Audit
timestamp không null. RLS chỉ cho phép truy cập phía service, không cấp quyền cho
`anon` hoặc `authenticated`.

Nhóm giá gồm return lag 1/3/5/10 phiên, SMA20/SMA50 và khoảng cách, Wilder RSI14,
MACD(12,26,9), độ lệch chuẩn return 20 phiên và drawdown 20/60 phiên so với rolling
maximum. Breadth dùng `advances + no_changes + declines`, net advance, tỷ lệ thành
phần, limit balance và trung bình 5/10 phiên của breadth ratio. Liquidity dùng
trung bình/tỷ lệ total volume và value 20 phiên cùng tỷ trọng match/deal. Không
tạo OHLC, ATR, candle, raw JSON hoặc phiên bị thiếu.

Input thiếu giữ `NULL`; số đếm zero hợp lệ vẫn là zero. Mẫu số zero hoặc null cho
kết quả `NULL`. Rolling result giữ `NULL` cho tới khi đủ window. NaN/infinity được
đổi thành `NULL`. Mỗi lần tính có thể đọc tối đa 250 phiên clean trước đó nhưng
chỉ ghi range yêu cầu, bảo đảm kết quả overlap của incremental/backfill giống nhau.

## Vận hành

Apply thủ công `migrations/20260826_create_index_features_daily.sql`, sau đó chạy:

```bash
python main.py index-features-preview --date 25/08/2026 --indexes VNINDEX
python main.py index-features-daily --date 25/08/2026 --indexes VNINDEX
python main.py index-features-backfill --from 05/01/2026 --to 25/08/2026 --indexes VNINDEX
python main.py index-features-check --from 05/01/2026 --to 25/08/2026 --indexes VNINDEX
```

Preview và check chỉ đọc. Muốn có lịch sử dài hơn, hãy backfill clean
`index_daily` trước, rồi backfill index feature và chạy check. Ngày raw-không-clean
được báo riêng và không bao giờ tạo feature row.
