# Quy ước dữ liệu

## Mục đích

Tài liệu này định nghĩa các quy ước dữ liệu cho TradingTPlus trong Phase 0. Mục
tiêu là bảo vệ độ đúng của dữ liệu raw/clean và hướng dẫn công việc sau này về
feature, signal, backtest, kiểm tra completeness và alert. Các quy ước mô tả ý
nghĩa dữ liệu; chúng không cho phép thay đổi schema hoặc ghi lại dữ liệu.

## Nguồn sự thật

- Dữ liệu raw giữ payload SSI/API và thông tin truy vết ingest.
- Dữ liệu clean chứa các dòng đã normalize cho nghiên cứu và feature pipeline.
- `stock_daily` là nguồn daily chuẩn cho feature `1d`.
- `stock_intraday` chỉ lưu nến clean `1m`.
- Timeframe intraday cao hơn như `5m`, `15m`, `60m` được tạo từ
  `stock_intraday` trong bước tính feature.
- Không tạo feature `1d` chuẩn bằng cách aggregate nến intraday.

## Quy ước thời gian và múi giờ

- Dùng `Asia/Ho_Chi_Minh` để diễn giải phiên thị trường Việt Nam và hiển thị giờ
  giao dịch cho người dùng.
- PostgreSQL/Supabase có thể hiển thị giá trị `timestamptz` theo UTC. Việc hiển
  thị UTC không có nghĩa thời gian nến bị sai.
- `stock_intraday.time` là timestamp thị trường/nến.
- `stock_intraday.time` là nguồn sự thật cho thứ tự intraday, aggregation,
  completeness, feature, signal, backtest và live alert.
- `2026-07-15T02:15:00+00:00` tương đương
  `2026-07-15 09:15:00 Asia/Ho_Chi_Minh`.
- Luôn giữ timestamp có timezone. Không chuyển thành datetime naive.
- Không lưu timestamp thị trường thành text chỉ để hình thức hiển thị giống giờ
  Việt Nam.
- Không cộng thủ công bảy giờ. Hãy chuyển đổi timezone.

Ví dụ chuyển đổi đúng bằng pandas:

```python
time_utc = pd.to_datetime(df["time"], utc=True)
time_vn = time_utc.dt.tz_convert("Asia/Ho_Chi_Minh")
```

Dùng timestamp Việt Nam đã chuyển đổi để xác định ngày giao dịch, phân loại
phiên, hiển thị giờ giao dịch hoặc áp dụng ranh giới phiên. Khi contract của
pipeline yêu cầu UTC, giữ timestamp UTC có timezone để lưu trữ, so sánh và
serialize ổn định.

## Timestamp thị trường và timestamp audit

Timestamp thị trường cho biết dữ liệu thị trường áp dụng tại thời điểm nào.
Timestamp audit cho biết ứng dụng fetch, nhận, tạo, cập nhật hoặc tính một dòng
tại thời điểm nào. Hai nhóm này không thể thay thế nhau.

| Cột | Ý nghĩa | Cách dùng hợp lệ đối với thời gian thị trường |
| --- | --- | --- |
| `stock_intraday.time` | Timestamp thị trường/nến intraday | Thứ tự, aggregation, completeness, feature, signal, backtest và alert |
| `created_at` | Thời điểm ứng dụng insert lần đầu | Chỉ audit |
| `updated_at` | Thời điểm application upsert gần nhất | Chỉ audit |
| `fetched_at` | Thời điểm fetch raw | Chỉ truy vết ingest |
| `received_at` | Thời điểm nhận/capture streaming | Chỉ audit transport/capture; không thay thế timestamp thị trường từ nguồn |
| `last_updated_at` | Thời điểm tính/upsert feature | Chỉ audit độ mới của feature |

Không suy ra thứ tự nến, ngày giao dịch, nến aggregate, thời điểm signal, điểm
vào/ra backtest hoặc giờ thị trường của alert từ timestamp audit. Retry hoặc
backfill trễ có thể làm timestamp audit muộn hơn nhiều so với sự kiện thị trường.

## Ngày giao dịch, phiên và aggregation

- Xác định ngày giao dịch theo `Asia/Ho_Chi_Minh`, không chỉ dựa vào ngày UTC.
- Ngày trong tuần không chứng minh có phiên giao dịch; phải xử lý rõ holiday,
  halt, phiên rút ngắn, auction và response nguồn bị thiếu.
- Tạo timeframe intraday cao hơn từ nến clean `stock_intraday` `1m`.
- Không aggregate xuyên ngày giao dịch Việt Nam, ranh giới phiên hoặc giờ nghỉ
  trưa.
- Phải định nghĩa timestamp của nến aggregate là đầu hay cuối nến trước khi sử
  dụng và áp dụng nhất quán.
- Tính toán live/alert phải dùng nến đã đóng hoặc đánh dấu rõ nến chưa hoàn tất.

## Dữ liệu thiếu và không hợp lệ

- Không tạo dòng giả cho cuối tuần, ngày lễ, response rỗng hoặc endpoint không
  được hỗ trợ.
- Không âm thầm thay giá, volume, value hoặc flow bị thiếu bằng 0.
- Không forward-fill OHLCV trừ khi có contract nghiên cứu yêu cầu rõ ràng.
- Parse timestamp nguồn một cách tường minh. Reject hoặc quarantine timestamp
  không hợp lệ; không thay bằng thời gian hiện tại hay timestamp audit.
- Đánh giá completeness theo symbol, ngày giao dịch Việt Nam, phiên dự kiến và
  source/timeframe. Không có một số lượng nến cố định áp dụng cho mọi trường hợp.

## Đơn vị và nguồn gốc

Ghi nhận và giữ rõ field do sàn cung cấp hay được suy ra. Không nhầm volume từng
nến với volume lũy kế và không so sánh các value khác đơn vị khi chưa normalize.

Với dòng intraday normalize hiện tại, `value` là giá trị ước tính
`round(close * volume)`, không phải turnover chính xác do sàn cung cấp. Giữ
`NULL` khi `close` hoặc `volume` thiếu/không hợp lệ; không thay bằng 0.

## Checklist sử dụng downstream

Trước khi làm completeness, feature, signal, backtest hoặc live alert:

1. Dùng đúng bảng chuẩn và timestamp thị trường.
2. Parse timestamp có timezone và chuyển sang `Asia/Ho_Chi_Minh` cho logic ngày
   giao dịch/phiên.
3. Không dùng timestamp audit làm trình tự thời gian thị trường.
4. Tôn trọng ranh giới symbol, ngày giao dịch, phiên, giờ nghỉ trưa và timeframe.
5. Giữ trạng thái thiếu/không hỗ trợ và provenance.
6. Ngăn look-ahead từ nến tương lai hoặc thông tin audit.
7. Test timestamp UTC/Việt Nam tương đương, ranh giới ngày/phiên, rerun và
   backfill.

Các quy ước này chỉ là tài liệu. Không cần migration, thay đổi dữ liệu hoặc
backfill.

Feature aggregate giữ `stock_intraday.time` làm bucket start theo giờ Việt Nam biểu diễn UTC. Production feature chỉ ghi bucket đã đóng theo biên phiên phù hợp; partial aggregate quan sát được không chứng minh bucket đã đóng.
