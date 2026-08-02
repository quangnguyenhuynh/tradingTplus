# Feature pipeline

Feature pipeline chuyển **dữ liệu thị trường clean** thành các chỉ số xác định
(deterministic) để tầng signal và backtest sau này sử dụng. Ingest và tính
feature là hai công việc tách biệt:

- ingest thu thập và chuẩn hóa dữ liệu nguồn, không tính feature;
- command feature đọc bảng clean và ghi các row đã tính;
- command feature không tạo signal và không chạy backtest.

Nhờ tách riêng, có thể chạy lại feature mà không gọi lại SSI hoặc thay đổi dữ
liệu nguồn clean.

## Luồng dữ liệu và timeframe

```text
stock_daily --------------------------------------> feature 1d
                                                        |
stock_intraday (lưu nến nguồn 1m)                       v
        |                                         bảng features
        +-- aggregate trong memory --> feature 15m (symbol, timeframe, time)
        +-- aggregate trong memory --> feature 60m
```

Mọi kết quả được upsert vào một bảng `features`. Conflict key là
`(symbol, timeframe, time)`. Nến đã aggregate không được ghi ngược vào
`stock_intraday`.

| Timeframe | Ý nghĩa | Dữ liệu nguồn hay output được lưu? |
| --- | --- | --- |
| `1d` | Xu hướng, động lượng, thanh khoản và bối cảnh chính cho T+3/T+5. | Output feature được lưu, chỉ tính từ `stock_daily`. |
| `60m` | Xác nhận diễn biến rộng hơn trong phiên và hỗ trợ timing. | Output feature được lưu, aggregate từ nến clean 1m. |
| `15m` | Timing chi tiết hơn trong phiên. | Output feature được lưu, aggregate từ nến clean 1m. |
| `1m` | Dữ liệu nguồn intraday clean chuẩn. | Lưu trong `stock_intraday`, **không** lưu thành row feature. |
| `5m` | Độ phân giải calculator cấp thấp còn dùng cho nghiên cứu/test. | **Không** lưu thành row feature production. |

Production runner chỉ chấp nhận output feature `1d`, `15m`, `60m`. Pipeline
không bao giờ tính feature `1d` chuẩn từ intraday và từ chối persist feature
`1m` hoặc `5m`.

## Các mode thực thi

| Mode | Dùng khi nào | Dữ liệu đọc | Dữ liệu ghi | Có xóa dữ liệu không? |
| --- | --- | --- | --- | --- |
| `incremental` | Cập nhật hằng ngày hoặc backfill một khoảng ngày gồm cả hai đầu. | Target cùng lịch sử cần thiết để indicator đúng. | Chỉ row sau watermark đến target; nếu chưa có watermark thì chỉ ngày target. Command range chỉ ghi range được yêu cầu. | Không. Pipeline upsert. |
| `full` | Tính lại toàn bộ lịch sử hiện có của symbol/timeframe được chọn. | Toàn bộ lịch sử nguồn đã chọn. | Mọi row tính được trong lịch sử đó. | Không. Pipeline upsert và giữ nguyên row nằm ngoài kết quả tính. |
| `replace` / `rebuild-clean` | Thay một stream sai có giới hạn chính xác sau khi migration RPC đã được verify trong môi trường đó. | Scope nguồn chính xác cùng warm-up deterministic. | Một range UTC nửa mở của đúng symbol/timeframe qua một RPC atomic. | Có, chỉ trong transaction RPC; insert lỗi sẽ rollback phần delete. |

**Upsert** nghĩa là insert key chưa có hoặc update key trùng. Upsert không phải
xóa toàn bộ rồi dựng lại.

### Incremental: watermark và warm-up

**Watermark** là `features.time` mới nhất đã lưu của đúng một cặp
`symbol + timeframe`. Mỗi stream có watermark riêng. Pipeline dùng mốc này để
biết output mới bắt đầu từ đâu.

**Warm-up** là dữ liệu clean cũ được đọc thêm để EMA50, RSI14, MACD và so sánh
20 bar tính đúng. Đọc warm-up không có nghĩa là ghi lại warm-up:

- `1d` đọc tối đa 5 năm từ `stock_daily`, neo tại watermark (hoặc target date
  nếu chưa có watermark);
- `15m` và `60m` đọc tối đa 250 ngày giao dịch Việt Nam đã quan sát gần nhất từ
  `stock_intraday` 1m, kết thúc tại target date; mọi candle của phiên cũ nhất
  được chọn vẫn được lấy đủ dù phiên đó vắt qua page boundary;
- pipeline tính trên window đã load nhưng chỉ upsert vùng target mới hoặc bị
  ảnh hưởng.

Reader PostgREST an toàn khi server cap thấp hơn page size yêu cầu: query dùng
ordering ổn định, offset tăng theo số row thực trả và chỉ trang rỗng (hoặc exact
limit) kết thúc việc đọc. Trang lặp làm fail rõ ràng thay vì loop hoặc âm thầm
deduplicate.

Ví dụ: giả sử `SSI/1d` có watermark **30/07/2026** và dữ liệu clean đã có
**31/07/2026**. Lần chạy incremental target 31/07/2026 đọc thêm các row
`stock_daily` cũ làm warm-up, tính indicator trên window đó, rồi chỉ upsert row
sau 30/07/2026 đến hết 31/07/2026. Pipeline không ghi lại 5 năm warm-up. Nếu
`SSI/1d` chưa có watermark, command đó chỉ ghi ngày 31/07/2026.

### Full không phá hủy dữ liệu

Full đọc toàn bộ lịch sử hiện có của symbol được chọn, tính lại và upsert mọi
row tính được. Full **không** delete trước và không phải replace. Nếu database
có row feature cũ nằm ngoài kết quả vừa tính, full giữ nguyên row đó.

CLI không cho dùng `--mode full` cùng `--date` hoặc `--from/--to`. Muốn tính lại
một khoảng ngày nhưng không xóa row cũ, dùng command range bên dưới.

### Replace / rebuild-clean hoạt động sau khi deploy migration

> **Trạng thái hiện tại:** replace/rebuild-clean compute và validate dataset đúng scope, sau đó gọi đúng một RPC atomic chỉ dành cho service role.

Scope bắt buộc gồm đúng:

- một symbol;
- một timeframe được persist (`1d`, `15m` hoặc `60m`);
- thời điểm/ngày bắt đầu (`--from`);
- thời điểm/ngày kết thúc (`--to`), với start không sau end.

Scope thiếu hoặc quá rộng bị từ chối. Dataset hợp lệ, không rỗng được gửi bằng đúng một RPC sau khi deploy migration.

## Nên dùng mode nào?

- **Cập nhật hằng ngày:** dùng `incremental` với `--date`.
- **Tính lại một khoảng lịch sử mà không xóa row:** dùng command range
  `--from/--to`.
- **Tính lại toàn bộ lịch sử đã chọn:** dùng `full`.
- **Xóa và thay row sai:** deploy migration RPC atomic rồi dùng `replace` với scope chính xác.
- Không dùng `full` với kỳ vọng nó sẽ xóa row cũ.

## Hướng dẫn CLI thực tế

Ngày dùng định dạng `DD/MM/YYYY`. Nếu bỏ `--symbols`, runner tự resolve tất cả
symbol. Các command dưới đây khớp parser hiện tại.

### Daily incremental

```bash
python main.py features-daily --mode incremental --date 31/07/2026 --symbols SSI HPG
```

Đọc `stock_daily`, tính `1d`, chỉ upsert row sau watermark `1d` của từng symbol
đến target date. Nếu chưa có watermark, chỉ ghi target date. Không xóa row.

### Intraday 15m incremental

```bash
python main.py features-intraday --mode incremental --date 31/07/2026 --symbols SSI HPG --timeframes 15m
```

Đọc nến clean `stock_intraday` 1m cùng context `stock_daily`, aggregate bucket
15m đã đóng và upsert vùng target sau từng watermark `15m`. Không xóa row.

### Intraday 60m incremental

```bash
python main.py features-intraday --mode incremental --date 31/07/2026 --symbols SSI HPG --timeframes 60m
```

Đọc cùng nguồn clean, aggregate bucket 60m đã đóng và upsert vùng target sau
từng watermark `60m`. Không xóa row. Khi chạy trong ngày, có thể thêm
`--as-of 14:30` làm cutoff theo giờ Việt Nam; chỉ bucket đã đóng trước cutoff
được ghi.

### Khoảng lịch sử gồm cả hai đầu

```bash
python main.py features-daily --from 01/07/2026 --to 31/07/2026 --symbols SSI
python main.py features-intraday --from 01/07/2026 --to 31/07/2026 --symbols SSI --timeframes 15m 60m
```

Đây là range backfill tường minh, không phải mode `full`. Daily đọc toàn bộ
lịch sử `stock_daily` trước đó đến end date. Intraday đọc lịch sử nguồn 1m đến
end date. Cả hai tính với lịch sử cũ nhưng chỉ upsert range được yêu cầu, gồm cả
hai đầu, và không xóa gì. `--from-date`/`--to-date` là alias tương đương.
Không dùng được `--as-of` với range.

### Tính lại full

```bash
python main.py features-daily --mode full --symbols SSI
python main.py features-intraday --mode full --symbols SSI --timeframes 15m 60m
```

Command đầu đọc toàn bộ `stock_daily` đã chọn và upsert `1d`. Command sau đọc
toàn bộ lịch sử clean 1m đã chọn và upsert feature `15m`/`60m` đã đóng. Không
command nào xóa row hiện có.

### Chạy replace atomic theo scope

```bash
python main.py features-daily --mode replace --from 01/07/2026 --to 31/07/2026 --symbols SSI
python main.py features-intraday --mode rebuild-clean --from 01/07/2026 --to 31/07/2026 --symbols SSI --timeframes 15m
```

Hai command compute và validate toàn bộ output đúng scope trước khi gọi đúng một RPC atomic; phải deploy migration trước.

Command compatibility vẫn hỗ trợ nhiều persisted timeframe:

```bash
python main.py features --mode incremental --date 31/07/2026 --symbols SSI --timeframes 15m 60m 1d
```

Nên dùng command riêng theo nguồn ở trên nếu chỉ chạy daily hoặc intraday. Muốn
thu thập nến nguồn 1m, dùng ingest riêng:

```bash
python main.py intraday-ingest 31/07/2026 --symbols SSI
```

## Các feature hiện được tính

Mọi row được persist chứa OHLCV/value khi có dữ liệu và các nhóm dưới đây. Row
đầu có thể hợp lệ dù một số indicator là `NULL` vì chưa đủ warm-up.

### Daily và intraday dùng chung

- **Giá và lợi suất:** `return_from_open`, `return_from_prev_close`; đo mức thay
  đổi từ giá mở cửa phiên và giá đóng cửa daily trước đó.
- **Xu hướng:** `ema9`, `ema20`, `ema50`, `ema9_above_ema20`,
  `ema20_above_ema50`; mô tả hướng và thứ tự EMA.
- **Động lượng:** `rsi14`, `macd`, `macd_signal`, `macd_histogram`; mô tả tốc độ
  và hướng biến động giá.
- **Thanh khoản:** `volume_ma20`, `volume_ratio`, `value_ma20`, `value_ratio`;
  so sánh hoạt động hiện tại với baseline 20 quan sát.
- **Vùng giá/breakout:** `high_20_bars`, `low_20_bars`,
  `close_above_high_20`, `close_below_low_20`; so close với 20 bar trước, không
  đưa bar hiện tại vào vùng so sánh.
- **Hình dạng nến:** `candle_range`, `candle_body`, `candle_body_pct`,
  `close_position_in_candle`; mô tả biên độ, thân nến và vị trí close.

### Hành vi riêng của daily

Row daily dùng OHLCV/value từ `stock_daily`. Các field chỉ có ý nghĩa intraday
gồm `return_1m`, `return_5m`, `return_15m`, `vwap_intraday`,
`close_above_vwap`, `distance_to_vwap_pct` đều là `NULL` trên output `1d`.

### Hành vi riêng của intraday

- `return_1m`, `return_5m`, `return_15m` là lợi suất wall-clock cùng phiên khi
  phù hợp; field ngắn hơn output bar là `NULL` khi không có ý nghĩa (ví dụ
  return 1m/5m trên row 15m).
- `vwap_intraday`, `close_above_vwap`, `distance_to_vwap_pct` mô tả vị trí so
  với VWAP intraday ước tính và reset mỗi ngày giao dịch.
- Volume/value 15m/60m là tổng từ các nến nguồn clean 1m.
- `volume_ma20`/`value_ma20` intraday so cùng bucket giờ địa phương qua các ngày
  quan sát trước. `return_from_open` dùng open chính thức từ context
  `stock_daily` khi có.

Input thiếu giữ `NULL`, không đổi thành 0. `stock_intraday.value` clean hiện là
ước tính từ `round(close * volume)`, nên các feature value/VWAP dẫn xuất cũng có
cùng provenance.

## Kiểm tra kết quả sau khi chạy

Trước hết đọc summary của command: kiểm tra `status`, `total_records`,
`records_by_timeframe` và lỗi theo symbol. Sau đó dùng SQL read-only theo schema
hiện tại. Điều chỉnh symbol và timestamp UTC cho khoảng phiên Việt Nam cần kiểm
tra.

```sql
-- Kiểm tra symbol, timeframe, khoảng yêu cầu và row mới nhất.
select symbol, timeframe, min(time) as first_time, max(time) as latest_time,
       count(*) as row_count
from public.features
where symbol = 'SSI'
  and timeframe in ('1d', '15m', '60m')
  and time >= '2026-07-01T00:00:00Z'
  and time <  '2026-08-01T00:00:00Z'
group by symbol, timeframe
order by symbol, timeframe;

-- Key feature thực tế không được có duplicate.
select symbol, timeframe, time, count(*)
from public.features
group by symbol, timeframe, time
having count(*) > 1;

-- Xem NULL hợp lệ và bất thường ở các row mới nhất.
select symbol, timeframe, time, close, ema50, rsi14, macd,
       volume_ma20, vwap_intraday
from public.features
where symbol = 'SSI' and timeframe = '15m'
order by time desc
limit 20;

-- Xác nhận watermark mới nhất của từng stream được persist.
select symbol, timeframe, max(time) as watermark
from public.features
where symbol = 'SSI'
group by symbol, timeframe
order by timeframe;
```

Phải đọc `NULL` theo context: row đầu có thể thiếu EMA/RSI/MACD/indicator 20 bar;
mọi cột return intraday và VWAP phải là `NULL` trên `1d`; key bắt buộc bị thiếu
hoặc indicator đã ổn định bỗng thành `NULL` cần được điều tra.

## Lỗi thường gặp

- **Chưa có row clean nguồn:** chạy và validate daily/intraday ingest riêng
  trước. Feature không tạo giả dữ liệu nguồn thiếu.
- **Chạy nhầm timeframe:** dùng `features-daily` cho `1d` và
  `features-intraday --timeframes 15m 60m` cho output intraday.
- **Mong đợi `1m`/`5m` trong `features`:** 1m là timeframe nguồn clean, còn 5m
  không phải feature production được persist. Bị từ chối là đúng thiết kế.
- **Nhầm full là delete + rebuild:** full chỉ upsert, không xóa row stale nằm
  ngoài kết quả tính.
- **Indicator đầu range là `NULL`:** rolling indicator cần warm-up. Hãy kiểm tra
  lịch sử nguồn trước khi kết luận đây là lỗi.
- **Replace bị từ chối:** bắt buộc đúng một symbol, một timeframe và đủ hai mốc;
  scope hợp lệ vẫn dừng an toàn vì chưa có atomic support.
- **Lỗi Supabase:** cài dependency và cung cấp `SUPABASE_URL` cùng Supabase key
  phù hợp qua environment. Không ghi credential vào command, log hoặc tài liệu.

## Bản đồ package

| File | Trách nhiệm |
| --- | --- |
| `daily.py` | Đọc `stock_daily`, tính `1d`, ghi `features`. |
| `intraday.py` | Đọc nến 1m, aggregate bucket đã đóng và tính feature intraday. |
| `backfill.py` | Tính một khoảng lịch sử gồm cả hai đầu và chỉ ghi range đó. |
| `common.py` | Công thức chung và chuẩn bị dataframe. |
| `runtime.py` | Đọc DB, watermark, warm-up, serialize, upsert, replace guard và summary. |
| `runner.py` | Orchestrator compatibility cho nhiều nguồn. |
| `policy.py` | Default timeframe được persist và chặn ghi 1m/5m. |

## Ảnh hưởng database và dữ liệu của tài liệu này

Thay đổi tài liệu không cần migration, không ghi database, không backfill dữ
liệu nguồn và không backfill feature. Row feature `1m`/`5m` cũ nếu có không bị
tự động xóa; cleanup cần một operation riêng được review.

## Atomic replace theo scope (Issue #110)

| Mode | Nguồn/warm-up | Mutation | Ý nghĩa cleanup |
| --- | --- | --- | --- |
| `full` | Toàn bộ history đã chọn | Upsert idempotent | Không xóa row stale. |
| `incremental` | Watermark riêng symbol/timeframe; daily 5 năm; intraday 250 phiên quan sát | Chỉ ghi row target mới/bị ảnh hưởng; không có source là no-op thành công | Không tự phát hiện historical correction khi source không có version metadata. |
| `replace` (alias `rebuild-clean`) | Compute warm-up cộng đúng output range | Một RPC `replace_features_atomic` sau khi validate toàn bộ | Atomically delete/insert đúng symbol/timeframe/range. |

Read `stock_daily` được phân trang deterministic theo `trading_date`; newest-N vẫn trả oldest-first cho calculator. Replace bắt buộc đúng một symbol, một timeframe `1d`/`15m`/`60m`, và ngày Việt Nam inclusive `--from`/`--to`; DB nhận `[start_utc, end_exclusive_utc)`. Dataset rỗng, duplicate, sai schema hoặc ngoài scope dừng trước mutation; không fallback delete/upsert trực tiếp.

```bash
python main.py features-daily --mode replace --from 01/07/2026 --to 31/07/2026 --symbols SSI
python main.py features-intraday --mode rebuild-clean --from 01/07/2026 --to 31/07/2026 --symbols SSI --timeframes 15m
```

Phải deploy `migrations/20260802_atomic_replace_features.sql` trước application code. Warm-up intraday là 250 phiên thực sự quan sát trong clean 1m, không phải ngày lịch hay bars. Không có row cần ghi và không lỗi trả `status=OK`, `no_op=true`. Dùng scoped replace cho historical correction đã biết; full chỉ recompute non-destructive.

Regression gate Phase 0 dùng 1.501 row daily ngày trong tuần không hằng và 251
phiên intraday quan sát. Sau serialization production sáu chữ số, target cuối
cho `1d`, `15m`, `60m` khớp full history ở mọi cột persisted, với chênh lệch
float tuyệt đối và tương đối lớn nhất bằng 0. Fixture 200 và 250 phiên đều khớp;
250 vẫn là default production. Với request 1.000 row, fixture intraday đọc 16
trang full, 12 trang cho 200 phiên và 15 trang cho 250 phiên. Xem
`docs/phase0/PHASE0_VALIDATION_REPORT.vi.md`; evidence offline này không thay thế
các gate live Phase 0 vẫn bị blocked.
