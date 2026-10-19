# Stock Screener V1

Bộ lọc kỹ thuật EOD **phục vụ nghiên cứu**, không tạo signal, backtest, xác suất,
xếp hạng, đề xuất NAV hoặc cảnh báo.

## Nguồn và phạm vi

- Chỉ đọc `stock_features` theo ngày giao dịch Việt Nam, `timeframe=1d`.
- Không tự chạy ingest hoặc feature.
- Chỉ xét mã trong `symbols.status=active`; `--symbols` giới hạn phạm vi.
- Thiếu feature đúng ngày thì `NOT_EVALUABLE`, không lấy dữ liệu ngày cũ thay thế.

## Quy tắc V1 (ngưỡng thử nghiệm, chưa backtest)

Cần đồng thời đạt 5 điều kiện:

1. Xu hướng: `close > ema20 > ema50`.
2. RSI14 từ 50 tới 70 (bao gồm biên).
3. `macd_histogram > 0`.
4. `volume_ratio >= 1`.
5. `value_ratio >= 1`.

Mỗi điều kiện đúng được 20 điểm; 0–100 **không phải xác suất lợi nhuận**.
Nếu dữ liệu yêu cầu thiếu hoặc không hợp lệ: `NOT_EVALUABLE`, điểm NULL,
ghi rõ trường thiếu. Nếu đủ dữ liệu: `PASS` hoặc `FAIL`.
Ngày không có bất kỳ feature nào được báo lỗi, không tạo dòng giả.

## Cách chạy

Xem trước, mặc định chỉ đọc:

```bash
python main.py stock-screener --date 13/08/2026 --symbols SSI
```

Sau khi **tự chạy migration** `migrations/20261017_create_stock_screener_results.sql`:

```bash
python main.py stock-screener --date 13/08/2026 --symbols SSI --apply
```

Upsert theo `symbol, trading_date, screener_version`. Bảng mới bật RLS và
backend service role mới được truy cập; app không ghi trực tiếp.
Chưa có lịch chạy tự động, backfill hoặc kích hoạt analysis/signal.

## V2: cấu hình trọng số và Methodology có phiên bản

Giữ nguyên V1 và mặc định CLI vẫn là V1. V2 là bộ lọc nghiên cứu độc lập,
định nghĩa bởi:
- [Cấu hình JSON](configs/v2.json) — code thực thi các quy tắc.
- [Phương pháp tiếng Việt](methodologies/v2.vi.md).
- [Phương pháp tiếng Anh](methodologies/v2.md).

Trọng số: xu hướng 40, RSI 15, MACD 20, khối lượng 10, giá trị 15;
PASS từ 70/100 nếu dữ liệu đầy đủ. Mỗi tiêu chí đạt được toàn bộ điểm,
không đạt được 0. Điểm không phải xác suất hay kết quả backtest.

Sau khi tự chạy migration `migrations/20261019_screener_v2_methodology.sql`,
xem phương pháp và đăng ký V2 bất biến trên DB:

```bash
python main.py stock-screener-config --version v2 --language vi
python main.py stock-screener-config --version v2 --apply
python main.py stock-screener --date 13/08/2026 --symbols SSI --version v2
python main.py stock-screener --date 13/08/2026 --symbols SSI --version v2 --apply
```

`config_hash` được tính từ JSON và hai bản Markdown để truy vết.
Không được sửa V2 sau khi đăng ký; thay đổi trọng số, ngưỡng hay nội dung
phương pháp đều phải tạo phiên bản mới. V1 không đổi; V2 không tự chạy
backtest, signal hoặc pipeline khác.
